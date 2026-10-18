package middleware_test

import (
	"bytes"
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"airpay/netbanking/internal/middleware"
)

func TestChainRunsTheFirstMiddlewareOutermost(t *testing.T) {
	var order []string
	tag := func(name string) middleware.Middleware {
		return func(next http.Handler) http.Handler {
			return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				order = append(order, name)
				next.ServeHTTP(w, r)
			})
		}
	}
	h := middleware.Chain(http.HandlerFunc(func(http.ResponseWriter, *http.Request) {
		order = append(order, "handler")
	}), tag("a"), tag("b"), tag("c"))

	h.ServeHTTP(httptest.NewRecorder(), httptest.NewRequest(http.MethodGet, "/", nil))

	if got := strings.Join(order, ","); got != "a,b,c,handler" {
		t.Errorf("order = %s", got)
	}
}

func TestAPanicBecomesAJSON500AndIsLoggedWithoutTheBody(t *testing.T) {
	var logs bytes.Buffer
	logger := slog.New(slog.NewTextHandler(&logs, nil))
	h := middleware.Chain(
		http.HandlerFunc(func(http.ResponseWriter, *http.Request) { panic("boom") }),
		middleware.Recover(logger),
	)
	rec := httptest.NewRecorder()

	h.ServeHTTP(rec, httptest.NewRequest(http.MethodPost, "/x?secret=1", strings.NewReader("password=pw")))

	if rec.Code != http.StatusInternalServerError || rec.Header().Get("Content-Type") != "application/json" {
		t.Errorf("%d %v", rec.Code, rec.Header())
	}
	if !strings.Contains(rec.Body.String(), `"success":false`) || strings.Contains(rec.Body.String(), "boom") {
		t.Errorf("body %s must be the standard error and must not leak the panic value", rec.Body)
	}
	if !strings.Contains(logs.String(), "boom") || strings.Contains(logs.String(), "password=pw") {
		t.Errorf("logs: %s", logs.String())
	}
}

func TestRequestLogSetsAnIDAndLogsTheStatus(t *testing.T) {
	var logs bytes.Buffer
	h := middleware.Chain(
		http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) { w.WriteHeader(http.StatusTeapot) }),
		middleware.RequestLog(slog.New(slog.NewTextHandler(&logs, nil))),
	)
	rec := httptest.NewRecorder()

	h.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/brew?token=secret", nil))

	id := rec.Header().Get("X-Request-Id")
	if len(id) != 16 || !strings.Contains(logs.String(), "request_id="+id) {
		t.Errorf("id %q, logs %s", id, logs.String())
	}
	if !strings.Contains(logs.String(), "status=418") || !strings.Contains(logs.String(), "path=/brew") ||
		strings.Contains(logs.String(), "secret") {
		t.Errorf("logs: %s", logs.String())
	}
}

func TestRequestLogDefaultsTheStatusTo200(t *testing.T) {
	var logs bytes.Buffer
	h := middleware.RequestLog(slog.New(slog.NewTextHandler(&logs, nil)))(
		http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) { _, _ = w.Write([]byte("ok")) }))

	h.ServeHTTP(httptest.NewRecorder(), httptest.NewRequest(http.MethodGet, "/", nil))

	if !strings.Contains(logs.String(), "status=200") {
		t.Errorf("logs: %s", logs.String())
	}
}

func TestMaxBodyStopsReadingAtTheLimit(t *testing.T) {
	var readErr error
	h := middleware.MaxBody(10)(http.HandlerFunc(func(_ http.ResponseWriter, r *http.Request) {
		_, readErr = io.ReadAll(r.Body)
	}))

	h.ServeHTTP(httptest.NewRecorder(), httptest.NewRequest(http.MethodPost, "/", strings.NewReader(strings.Repeat("a", 11))))

	if readErr == nil {
		t.Error("an 11 byte body must fail with a limit of 10")
	}
	readErr = nil
	h.ServeHTTP(httptest.NewRecorder(), httptest.NewRequest(http.MethodPost, "/", strings.NewReader(strings.Repeat("a", 10))))
	if readErr != nil {
		t.Errorf("a 10 byte body must pass: %v", readErr)
	}
}

func TestSecureHeaders(t *testing.T) {
	h := middleware.SecureHeaders()(http.HandlerFunc(func(http.ResponseWriter, *http.Request) {}))
	rec := httptest.NewRecorder()

	h.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/", nil))

	if rec.Header().Get("X-Content-Type-Options") != "nosniff" {
		t.Errorf("headers %v", rec.Header())
	}
}
