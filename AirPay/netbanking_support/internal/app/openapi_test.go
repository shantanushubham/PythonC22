package app_test

import (
	"encoding/json"
	"io"
	"log/slog"
	"sort"
	"strconv"
	"strings"
	"testing"
	"time"

	"airpay/netbanking/api"
	"airpay/netbanking/internal/app"
	"airpay/netbanking/internal/config"
	"airpay/netbanking/internal/testutil"
)

// These tests keep api/openapi.json, which is written by hand, and the real routes
// from drifting apart.

type spec struct {
	OpenAPI string                                `json:"openapi"`
	Paths   map[string]map[string]json.RawMessage `json:"paths"`
}

func loadSpec(t *testing.T) (spec, map[string]any) {
	t.Helper()
	var typed spec
	if err := json.Unmarshal(api.Spec, &typed); err != nil {
		t.Fatalf("api/openapi.json is not valid JSON: %v", err)
	}
	var raw map[string]any
	_ = json.Unmarshal(api.Spec, &raw)
	return typed, raw
}

var httpMethods = map[string]bool{"get": true, "put": true, "post": true, "delete": true, "patch": true, "head": true, "options": true}

func TestTheSpecDescribesExactlyTheDocumentedRoutes(t *testing.T) {
	controllers, err := app.NewControllers(
		config.Config{BaseURL: baseURL, PaymentTTL: time.Minute},
		app.Dependencies{
			Payments: testutil.NewMemoryPaymentRepository(),
			Logger:   slog.New(slog.NewTextHandler(io.Discard, nil)),
		})
	if err != nil {
		t.Fatal(err)
	}
	var inCode []string
	for _, route := range controllers.Routes() {
		if route.InSpec {
			inCode = append(inCode, route.Method+" "+route.Path)
		}
	}

	doc, _ := loadSpec(t)
	var inSpec []string
	for path, item := range doc.Paths {
		for method := range item {
			if httpMethods[method] {
				inSpec = append(inSpec, strings.ToUpper(method)+" "+path)
			}
		}
	}

	sort.Strings(inCode)
	sort.Strings(inSpec)
	if strings.Join(inCode, "\n") != strings.Join(inSpec, "\n") {
		t.Errorf("spec and routes differ.\nroutes:\n%s\nspec:\n%s", strings.Join(inCode, "\n"), strings.Join(inSpec, "\n"))
	}
	if len(inCode) == 0 {
		t.Error("no routes found")
	}
}

func TestOperationIDsAreUniqueAndPresent(t *testing.T) {
	_, raw := loadSpec(t)
	seen := map[string]string{}
	for path, item := range raw["paths"].(map[string]any) {
		for method, op := range item.(map[string]any) {
			if !httpMethods[method] {
				continue
			}
			id, _ := op.(map[string]any)["operationId"].(string)
			if id == "" {
				t.Errorf("%s %s has no operationId", method, path)
			} else if other, dup := seen[id]; dup {
				t.Errorf("operationId %q is used by %s and %s %s", id, other, method, path)
			}
			seen[id] = method + " " + path
		}
	}
}

func TestEveryRefInTheSpecResolves(t *testing.T) {
	_, raw := loadSpec(t)
	var refs []string
	var walk func(any)
	walk = func(node any) {
		switch v := node.(type) {
		case map[string]any:
			for k, child := range v {
				if ref, ok := child.(string); ok && k == "$ref" {
					refs = append(refs, ref)
				}
				walk(child)
			}
		case []any:
			for _, child := range v {
				walk(child)
			}
		}
	}
	walk(raw)

	if len(refs) == 0 {
		t.Fatal("expected the spec to use $ref")
	}
	for _, ref := range refs {
		var node any = raw
		for _, part := range strings.Split(strings.TrimPrefix(ref, "#/"), "/") {
			m, ok := node.(map[string]any)
			if !ok || m[part] == nil {
				t.Errorf("%s does not resolve (stopped at %q)", ref, part)
				break
			}
			node = m[part]
		}
	}
}

func TestEveryOperationDocumentsItsSuccessAndErrorResponses(t *testing.T) {
	_, raw := loadSpec(t)
	for path, item := range raw["paths"].(map[string]any) {
		for method, op := range item.(map[string]any) {
			if !httpMethods[method] {
				continue
			}
			responses, _ := op.(map[string]any)["responses"].(map[string]any)
			hasSuccess, hasError := false, false
			for code := range responses {
				hasSuccess = hasSuccess || strings.HasPrefix(code, "2")
				hasError = hasError || strings.HasPrefix(code, "4") || strings.HasPrefix(code, "5")
			}
			if path == "/health" {
				hasError = true // a liveness probe has no error response to document
			}
			if !hasSuccess || !hasError {
				t.Errorf("%s %s: responses %v need a 2xx and an error", method, path, responses)
			}
		}
	}
}

func TestEveryDocumentedStatusIsReallyReturned(t *testing.T) {
	// Spot check the responses the spec promises for POST /api/v1/payments.
	_, raw := loadSpec(t)
	post := raw["paths"].(map[string]any)["/api/v1/payments"].(map[string]any)["post"].(map[string]any)
	documented := post["responses"].(map[string]any)
	s := newServer(t)
	s.postJSON(validBody, "Idempotency-Key", "k")

	actual := map[string]int{
		"201": s.postJSON(validBody).Code,
		"200": s.postJSON(validBody, "Idempotency-Key", "k").Code,
		"400": s.postJSON("{").Code,
		"409": s.postJSON(strings.Replace(validBody, "1500.50", "2", 1), "Idempotency-Key", "k").Code,
		"413": s.postJSON(`{"reference":"` + strings.Repeat("a", 2<<20) + `"}`).Code,
		"503": s.postJSON(`{"amount":"10","bank_code":"BKID","return_url":"https://x.example"}`).Code,
	}
	for code, got := range actual {
		if documented[code] == nil {
			t.Errorf("the spec does not document %s", code)
		}
		if strconv.Itoa(got) != code {
			t.Errorf("expected %s, got %d", code, got)
		}
	}
}
