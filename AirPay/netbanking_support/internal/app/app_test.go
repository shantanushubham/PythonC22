package app_test

import (
	"bytes"
	"encoding/json"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"

	"airpay/netbanking/internal/app"
	"airpay/netbanking/internal/config"
	"airpay/netbanking/internal/model"
	"airpay/netbanking/internal/repository"
	"airpay/netbanking/internal/service"
	"airpay/netbanking/internal/testutil"
)

const baseURL = "http://nb.test"

// syncBuffer is a log destination that is safe to write from many requests at once.
type syncBuffer struct {
	mu  sync.Mutex
	buf bytes.Buffer
}

func (b *syncBuffer) Write(p []byte) (int, error) {
	b.mu.Lock()
	defer b.mu.Unlock()
	return b.buf.Write(p)
}

func (b *syncBuffer) String() string {
	b.mu.Lock()
	defer b.mu.Unlock()
	return b.buf.String()
}

// server is the whole service behind an http.Handler, with a fake clock and fake ids.
type server struct {
	t       *testing.T
	handler http.Handler
	clock   *testutil.FakeClock
	repo    repository.PaymentRepository
	logs    *syncBuffer
}

type option func(*app.Dependencies)

func newServer(t *testing.T, opts ...option) *server {
	t.Helper()
	logs := &syncBuffer{}
	clock := testutil.NewFakeClock()
	deps := app.Dependencies{
		Payments: testutil.NewMemoryPaymentRepository(),
		Clock:    clock,
		IDs:      &testutil.SequentialIDs{},
		Logger:   slog.New(slog.NewTextHandler(logs, nil)),
	}
	for _, opt := range opts {
		opt(&deps)
	}
	cfg := config.Config{Port: "8002", BaseURL: baseURL, PaymentTTL: 15 * time.Minute, DownBanks: []string{"BKID"}}
	handler, err := app.NewHandler(cfg, deps)
	if err != nil {
		t.Fatal(err)
	}
	return &server{t: t, handler: handler, clock: clock, repo: deps.Payments, logs: logs}
}

type response struct {
	*httptest.ResponseRecorder
}

func (r response) json() map[string]any {
	var out map[string]any
	if err := json.Unmarshal(r.Body.Bytes(), &out); err != nil {
		panic("body is not JSON: " + r.Body.String())
	}
	return out
}

func (r response) data() map[string]any { return r.json()["data"].(map[string]any) }

func (r response) message() string { s, _ := r.json()["message"].(string); return s }

func (r response) fieldErrors() map[string]string {
	out := map[string]string{}
	list, _ := r.json()["errors"].([]any)
	for _, item := range list {
		e := item.(map[string]any)
		out[e["field"].(string)] = e["message"].(string)
	}
	return out
}

func (r response) location() string { return r.Header().Get("Location") }

func (s *server) do(method, path, body string, headers ...string) response {
	s.t.Helper()
	req := httptest.NewRequest(method, path, strings.NewReader(body))
	for i := 0; i+1 < len(headers); i += 2 {
		req.Header.Add(headers[i], headers[i+1])
	}
	rec := httptest.NewRecorder()
	s.handler.ServeHTTP(rec, req)
	return response{rec}
}

func (s *server) postJSON(body string, headers ...string) response {
	s.t.Helper()
	return s.do(http.MethodPost, "/api/v1/payments", body, append([]string{"Content-Type", "application/json"}, headers...)...)
}

func (s *server) postForm(path string, form url.Values) response {
	s.t.Helper()
	return s.do(http.MethodPost, path, form.Encode(), "Content-Type", "application/x-www-form-urlencoded")
}

func (s *server) login(id, customer, password string) response {
	return s.postForm("/bank/"+id+"/login", url.Values{"customer_id": {customer}, "password": {password}})
}

const validBody = `{"amount":"1500.50","bank_code":"HDFC","return_url":"https://shop.example.com/return","reference":"order_1001"}`

func (s *server) createPayment() string {
	s.t.Helper()
	res := s.postJSON(validBody)
	if res.Code != http.StatusCreated {
		s.t.Fatalf("create: %d %s", res.Code, res.Body)
	}
	return res.data()["transaction_id"].(string)
}

// --- creating payments ------------------------------------------------------------

func TestCreatePayment(t *testing.T) {
	s := newServer(t)

	res := s.postJSON(validBody)

	if res.Code != http.StatusCreated {
		t.Fatalf("status %d: %s", res.Code, res.Body)
	}
	if res.Header().Get("Content-Type") != "application/json" || res.Header().Get("Cache-Control") != "no-store" {
		t.Errorf("headers %v", res.Header())
	}
	if res.location() != "/api/v1/payments/nb_test_001" {
		t.Errorf("Location = %q", res.location())
	}
	if res.json()["success"] != true {
		t.Error("success must be true")
	}
	d := res.data()
	want := map[string]any{
		"transaction_id": "nb_test_001",
		"status":         "PENDING",
		"amount":         "1500.50",
		"currency":       "INR",
		"redirect_url":   baseURL + "/bank/nb_test_001",
		"return_url":     "https://shop.example.com/return",
		"reference":      "order_1001",
		"created_at":     "2026-10-18T12:00:00.000000Z",
		"expires_at":     "2026-10-18T12:15:00.000000Z",
	}
	for k, v := range want {
		if d[k] != v {
			t.Errorf("%s = %v, want %v", k, d[k], v)
		}
	}
	bank := d["bank"].(map[string]any)
	if bank["code"] != "HDFC" || bank["name"] != "HDFC Bank" {
		t.Errorf("bank = %v", bank)
	}
	for _, absent := range []string{"bank_reference", "failure_reason", "completed_at"} {
		if _, present := d[absent]; present {
			t.Errorf("%s must be absent for a pending payment", absent)
		}
	}
}

func TestAmountMayBeSentAsANumber(t *testing.T) {
	s := newServer(t)

	res := s.postJSON(`{"amount":99.5,"bank_code":"SBIN","return_url":"https://x.example/r"}`)

	if res.Code != http.StatusCreated || res.data()["amount"] != "99.50" {
		t.Errorf("%d %s", res.Code, res.Body)
	}
}

func TestValidation(t *testing.T) {
	cases := []struct {
		name  string
		body  string
		field string
		want  string
	}{
		{"zero amount", `{"amount":"0","bank_code":"SBIN","return_url":"https://x.example"}`, "amount", ""},
		{"negative amount", `{"amount":"-5","bank_code":"SBIN","return_url":"https://x.example"}`, "amount", ""},
		{"three decimals", `{"amount":"1.234","bank_code":"SBIN","return_url":"https://x.example"}`, "amount", ""},
		{"text amount", `{"amount":"abc","bank_code":"SBIN","return_url":"https://x.example"}`, "amount", ""},
		{"huge amount", `{"amount":"99999999999","bank_code":"SBIN","return_url":"https://x.example"}`, "amount", ""},
		{"missing amount", `{"bank_code":"SBIN","return_url":"https://x.example"}`, "amount", ""},
		{"unknown bank", `{"amount":"10","bank_code":"NOPE","return_url":"https://x.example"}`, "bank_code", ""},
		{"missing bank", `{"amount":"10","return_url":"https://x.example"}`, "bank_code", ""},
		{"usd", `{"amount":"10","currency":"USD","bank_code":"SBIN","return_url":"https://x.example"}`, "currency", ""},
		{"missing return_url", `{"amount":"10","bank_code":"SBIN"}`, "return_url", ""},
		{"javascript url", `{"amount":"10","bank_code":"SBIN","return_url":"javascript:alert(1)"}`, "return_url", ""},
		{"ftp url", `{"amount":"10","bank_code":"SBIN","return_url":"ftp://x.example/f"}`, "return_url", ""},
		{"credentials in url", `{"amount":"10","bank_code":"SBIN","return_url":"https://a:b@x.example"}`, "return_url", ""},
		{"bad reference", `{"amount":"10","bank_code":"SBIN","return_url":"https://x.example","reference":"a b!"}`, "reference", ""},
		{"long reference", `{"amount":"10","bank_code":"SBIN","return_url":"https://x.example","reference":"` + strings.Repeat("a", 65) + `"}`, "reference", ""},
		{"unknown field", `{"amount":"10","bank_code":"SBIN","return_url":"https://x.example","card":"4111"}`, "card", "unknown field"},
		{"wrong type", `{"amount":"10","bank_code":5,"return_url":"https://x.example"}`, "bank_code", "has the wrong type"},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			s := newServer(t)

			res := s.postJSON(c.body)

			if res.Code != http.StatusBadRequest {
				t.Fatalf("status %d: %s", res.Code, res.Body)
			}
			if res.json()["success"] != false {
				t.Error("success must be false")
			}
			got, ok := res.fieldErrors()[c.field]
			if !ok {
				t.Fatalf("no error for %q in %s", c.field, res.Body)
			}
			if c.want != "" && got != c.want {
				t.Errorf("message %q, want %q", got, c.want)
			}
		})
	}
}

func TestMalformedBodies(t *testing.T) {
	cases := map[string]string{
		"empty":            "",
		"not json":         "{amount:",
		"truncated":        `{"amount":"10"`,
		"array":            `[{"amount":"10"}]`,
		"null":             `null`,
		"two objects":      validBody + validBody,
		"trailing garbage": validBody + " x",
	}
	for name, body := range cases {
		s := newServer(t)

		res := s.postJSON(body)

		if res.Code != http.StatusBadRequest {
			t.Errorf("%s: status %d, want 400 (%s)", name, res.Code, res.Body)
		}
		if res.message() == "" {
			t.Errorf("%s: no message", name)
		}
	}
}

func TestAnOversizedBodyIsRejectedWith413(t *testing.T) {
	s := newServer(t)
	body := `{"amount":"10","reference":"` + strings.Repeat("a", 2<<20) + `"}`

	res := s.postJSON(body)

	if res.Code != http.StatusRequestEntityTooLarge {
		t.Errorf("status %d, want 413", res.Code)
	}
}

func TestEveryProblemIsReportedAtOnce(t *testing.T) {
	s := newServer(t)

	res := s.postJSON(`{"amount":"10","currency":"USD","bank_code":"NOPE","return_url":"ftp://x","reference":"a b"}`)

	got := res.fieldErrors()
	for _, field := range []string{"currency", "bank_code", "return_url", "reference"} {
		if got[field] == "" {
			t.Errorf("missing an error for %s: %v", field, got)
		}
	}
}

func TestABankThatIsDownGives503AndStoresNothing(t *testing.T) {
	s := newServer(t)

	res := s.postJSON(`{"amount":"10","bank_code":"BKID","return_url":"https://x.example"}`)

	if res.Code != http.StatusServiceUnavailable || !strings.Contains(res.message(), "Bank of India") {
		t.Errorf("%d %s", res.Code, res.Body)
	}
	if get := s.do(http.MethodGet, "/api/v1/payments/nb_test_001", ""); get.Code != http.StatusNotFound {
		t.Errorf("a payment exists for a bank that was down: %d", get.Code)
	}
}

// --- idempotency ------------------------------------------------------------------

func TestIdempotentReplay(t *testing.T) {
	s := newServer(t)
	first := s.postJSON(validBody, "Idempotency-Key", "order-1001")

	second := s.postJSON(validBody, "Idempotency-Key", "order-1001")

	if first.Code != http.StatusCreated || first.Header().Get("Idempotent-Replayed") != "" {
		t.Errorf("first: %d %v", first.Code, first.Header())
	}
	if second.Code != http.StatusOK || second.Header().Get("Idempotent-Replayed") != "true" {
		t.Errorf("second: %d %v", second.Code, second.Header())
	}
	if first.data()["transaction_id"] != second.data()["transaction_id"] {
		t.Error("the replay returned a different payment")
	}
}

func TestIdempotencyKeyReusedForADifferentRequestIs409(t *testing.T) {
	s := newServer(t)
	s.postJSON(validBody, "Idempotency-Key", "k1")

	res := s.postJSON(strings.Replace(validBody, "1500.50", "1.00", 1), "Idempotency-Key", "k1")

	if res.Code != http.StatusConflict {
		t.Errorf("status %d, want 409", res.Code)
	}
}

func TestBadIdempotencyKeyHeaders(t *testing.T) {
	s := newServer(t)

	if res := s.postJSON(validBody, "Idempotency-Key", "has space"); res.Code != http.StatusBadRequest {
		t.Errorf("invalid key: %d", res.Code)
	}
	if res := s.postJSON(validBody, "Idempotency-Key", "a", "Idempotency-Key", "b"); res.Code != http.StatusBadRequest {
		t.Errorf("two headers: %d", res.Code)
	}
	if res := s.postJSON(validBody, "Idempotency-Key", ""); res.Code != http.StatusBadRequest {
		t.Errorf("empty key: %d", res.Code)
	}
}

func TestReplayAfterTheCustomerPaidShowsSuccessWithoutARedirectURL(t *testing.T) {
	s := newServer(t)
	id := s.postJSON(validBody, "Idempotency-Key", "k").data()["transaction_id"].(string)
	s.login(id, "jane", "secret")

	replay := s.postJSON(validBody, "Idempotency-Key", "k")

	d := replay.data()
	if replay.Code != http.StatusOK || d["status"] != "SUCCESS" {
		t.Fatalf("%d %v", replay.Code, d["status"])
	}
	if _, present := d["redirect_url"]; present {
		t.Error("a finished payment must not offer a redirect_url")
	}
}

func TestTwentyConcurrentCreatesWithOneKeyMakeOnePayment(t *testing.T) {
	s := newServer(t)
	var (
		wg      sync.WaitGroup
		mu      sync.Mutex
		ids     = map[string]bool{}
		created int
	)
	start := make(chan struct{})
	for i := 0; i < 20; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			<-start
			res := s.postJSON(validBody, "Idempotency-Key", "same")
			mu.Lock()
			defer mu.Unlock()
			if res.Code != http.StatusCreated && res.Code != http.StatusOK {
				t.Errorf("status %d: %s", res.Code, res.Body)
				return
			}
			ids[res.data()["transaction_id"].(string)] = true
			if res.Code == http.StatusCreated {
				created++
			}
		}()
	}
	close(start)
	wg.Wait()

	if len(ids) != 1 || created != 1 {
		t.Errorf("%d payments, %d created; want 1 and 1", len(ids), created)
	}
}

// --- reading payments, banks, health -----------------------------------------------

func TestGetPayment(t *testing.T) {
	s := newServer(t)
	id := s.createPayment()

	res := s.do(http.MethodGet, "/api/v1/payments/"+id, "")

	if res.Code != http.StatusOK || res.data()["transaction_id"] != id || res.data()["status"] != "PENDING" {
		t.Errorf("%d %s", res.Code, res.Body)
	}
}

func TestGetUnknownPayment(t *testing.T) {
	s := newServer(t)

	res := s.do(http.MethodGet, "/api/v1/payments/nb_missing", "")

	if res.Code != http.StatusNotFound || res.json()["success"] != false {
		t.Errorf("%d %s", res.Code, res.Body)
	}
}

func TestWrongMethodsAndUnknownRoutesReturnJSON(t *testing.T) {
	s := newServer(t)

	put := s.do(http.MethodPut, "/api/v1/payments", "{}")
	del := s.do(http.MethodDelete, "/api/v1/payments/nb_x", "")
	postBanks := s.do(http.MethodPost, "/api/v1/banks", "")
	missing := s.do(http.MethodGet, "/nope", "")

	if put.Code != http.StatusMethodNotAllowed || put.Header().Get("Allow") != "POST" {
		t.Errorf("PUT: %d Allow=%q", put.Code, put.Header().Get("Allow"))
	}
	if del.Code != http.StatusMethodNotAllowed || del.Header().Get("Allow") != "GET, HEAD" {
		t.Errorf("DELETE: %d Allow=%q", del.Code, del.Header().Get("Allow"))
	}
	if postBanks.Code != http.StatusMethodNotAllowed {
		t.Errorf("POST banks: %d", postBanks.Code)
	}
	if missing.Code != http.StatusNotFound || missing.message() != "Route GET /nope not found" {
		t.Errorf("unknown route: %d %q", missing.Code, missing.message())
	}
	for _, res := range []response{put, del, postBanks, missing} {
		if res.Header().Get("Content-Type") != "application/json" || res.json()["success"] != false {
			t.Errorf("not the standard error body: %s", res.Body)
		}
	}
}

func TestListBanks(t *testing.T) {
	s := newServer(t)

	all := s.do(http.MethodGet, "/api/v1/banks", "")
	down := s.do(http.MethodGet, "/api/v1/banks?status=down", "")
	up := s.do(http.MethodGet, "/api/v1/banks?status=UP", "")
	bad := s.do(http.MethodGet, "/api/v1/banks?status=maybe", "")

	banks := func(r response) []any { return r.data()["banks"].([]any) }
	if len(banks(all)) != 16 {
		t.Errorf("%d banks, want 16", len(banks(all)))
	}
	if len(banks(down)) != 1 || banks(down)[0].(map[string]any)["code"] != "BKID" {
		t.Errorf("down = %v", banks(down))
	}
	if len(banks(up)) != 15 {
		t.Errorf("%d banks up, want 15", len(banks(up)))
	}
	if bad.Code != http.StatusBadRequest || bad.fieldErrors()["status"] == "" {
		t.Errorf("bad filter: %d %s", bad.Code, bad.Body)
	}
}

func TestHealth(t *testing.T) {
	s := newServer(t)

	res := s.do(http.MethodGet, "/health", "")

	body := res.json()
	if res.Code != http.StatusOK || body["status"] != "ok" || body["service"] != "netbanking-support" {
		t.Errorf("%d %s", res.Code, res.Body)
	}
	if len(body["banks"].([]any)) != 16 {
		t.Errorf("banks = %v", body["banks"])
	}
}

func TestEveryResponseCarriesARequestIDAndNosniff(t *testing.T) {
	s := newServer(t)

	for _, path := range []string{"/health", "/nope", "/bank/nb_missing"} {
		res := s.do(http.MethodGet, path, "")
		if res.Header().Get("X-Request-Id") == "" || res.Header().Get("X-Content-Type-Options") != "nosniff" {
			t.Errorf("%s: headers %v", path, res.Header())
		}
	}
}

func TestSpecAndDocsEndpoints(t *testing.T) {
	s := newServer(t)

	for _, path := range []string{"/openapi", "/openapi.json"} {
		res := s.do(http.MethodGet, path, "")
		if res.Code != http.StatusOK || res.json()["openapi"] == nil {
			t.Errorf("%s: %d", path, res.Code)
		}
	}
	docs := s.do(http.MethodGet, "/docs", "")
	if docs.Code != http.StatusOK || !strings.Contains(docs.Body.String(), "swagger") {
		t.Errorf("/docs: %d", docs.Code)
	}
}

// --- the bank's pages --------------------------------------------------------------

func TestLoginPage(t *testing.T) {
	s := newServer(t)
	id := s.createPayment()

	res := s.do(http.MethodGet, "/bank/"+id, "")

	if res.Code != http.StatusOK {
		t.Fatalf("status %d", res.Code)
	}
	page := res.Body.String()
	for _, want := range []string{"HDFC Bank", "1,500.50", "order_1001", `action="/bank/` + id + `/login"`, `name="password"`, `type="password"`} {
		if !strings.Contains(page, want) {
			t.Errorf("page does not contain %q", want)
		}
	}
	h := res.Header()
	checks := map[string]string{
		"Content-Type":            "text/html; charset=utf-8",
		"Cache-Control":           "no-store",
		"X-Frame-Options":         "DENY",
		"Referrer-Policy":         "no-referrer",
		"Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'",
	}
	for k, v := range checks {
		if h.Get(k) != v {
			t.Errorf("%s = %q, want %q", k, h.Get(k), v)
		}
	}
	if strings.Contains(strings.ToLower(page), "<script") {
		t.Error("the page must not contain scripts")
	}
}

func TestLoginPageForUnknownPaymentIsAnHTMLNotFound(t *testing.T) {
	s := newServer(t)

	res := s.do(http.MethodGet, "/bank/nb_missing", "")

	if res.Code != http.StatusNotFound || !strings.HasPrefix(res.Header().Get("Content-Type"), "text/html") ||
		!strings.Contains(res.Body.String(), "Payment not found") {
		t.Errorf("%d %s", res.Code, res.Body)
	}
}

func TestAttackerControlledTextIsEscaped(t *testing.T) {
	evil := `<script>alert(1)</script>`
	banks := repository.NewStaticBankRepository(
		[]model.Bank{{Code: "EVIL", Name: evil, Accent: "red;}</style><script>x</script>"}}, nil)
	s := newServer(t, func(d *app.Dependencies) { d.Banks = banks })
	res := s.postJSON(`{"amount":"10","bank_code":"EVIL","return_url":"https://x.example/r","reference":"ok_1"}`)
	id := res.data()["transaction_id"].(string)

	login := s.do(http.MethodGet, "/bank/"+id, "")
	notFound := s.do(http.MethodGet, "/bank/%3Cscript%3Ealert(2)%3C%2Fscript%3E", "")

	for name, page := range map[string]string{"login": login.Body.String(), "not found": notFound.Body.String()} {
		if strings.Contains(page, "<script>") {
			t.Errorf("%s page contains an unescaped script tag:\n%s", name, page)
		}
	}
	if !strings.Contains(login.Body.String(), "&lt;script&gt;") {
		t.Error("the bank name should appear escaped")
	}
}

func TestSuccessfulLoginRedirectsBackToTheMerchant(t *testing.T) {
	s := newServer(t)
	id := s.createPayment()

	res := s.login(id, "jane", "secret")

	if res.Code != http.StatusSeeOther {
		t.Fatalf("status %d: %s", res.Code, res.Body)
	}
	loc, err := url.Parse(res.location())
	if err != nil {
		t.Fatal(err)
	}
	q := loc.Query()
	if loc.Host != "shop.example.com" || loc.Path != "/return" ||
		q.Get("status") != "SUCCESS" || q.Get("transaction_id") != id || q.Get("reference") != "order_1001" {
		t.Errorf("redirected to %s", res.location())
	}
	got := s.do(http.MethodGet, "/api/v1/payments/"+id, "").data()
	if got["status"] != "SUCCESS" || !strings.HasPrefix(got["bank_reference"].(string), "HDFC") || got["completed_at"] == nil {
		t.Errorf("payment after login: %v", got)
	}
	if _, present := got["redirect_url"]; present {
		t.Error("a finished payment must not offer a redirect_url")
	}
}

func TestRedirectKeepsTheMerchantsExistingQuery(t *testing.T) {
	s := newServer(t)
	id := s.postJSON(`{"amount":"10","bank_code":"SBIN","return_url":"https://shop.example.com/r?cart=42&a=b%20c"}`).
		data()["transaction_id"].(string)

	res := s.login(id, "jane", "secret")

	q := mustParse(t, res.location()).Query()
	if q.Get("cart") != "42" || q.Get("a") != "b c" || q.Get("status") != "SUCCESS" {
		t.Errorf("query = %v", q)
	}
}

func mustParse(t *testing.T, raw string) *url.URL {
	t.Helper()
	u, err := url.Parse(raw)
	if err != nil {
		t.Fatal(err)
	}
	return u
}

func TestEachFailureScenario(t *testing.T) {
	cases := map[string]string{
		"insufficient": "Insufficient funds",
		"declined":     "Transaction declined by bank",
		"timeout":      "Bank server timeout",
		"locked":       "Customer account is locked",
		"limit":        "Transaction limit exceeded",
		"INSUFFICIENT": "Insufficient funds",
	}
	for customer, reason := range cases {
		s := newServer(t)
		id := s.createPayment()

		res := s.login(id, customer, "secret")

		if res.Code != http.StatusSeeOther || mustParse(t, res.location()).Query().Get("status") != "FAILED" {
			t.Errorf("%s: %d %s", customer, res.Code, res.location())
		}
		got := s.do(http.MethodGet, "/api/v1/payments/"+id, "").data()
		if got["status"] != "FAILED" || got["failure_reason"] != reason {
			t.Errorf("%s: %v", customer, got)
		}
		if _, present := got["bank_reference"]; present {
			t.Errorf("%s: a failed payment has a bank reference", customer)
		}
	}
}

func TestWrongPasswordShowsTheLoginAgainAndAllowsARetry(t *testing.T) {
	s := newServer(t)
	id := s.createPayment()

	bad := s.login(id, "jane", "wrong")
	status := s.do(http.MethodGet, "/api/v1/payments/"+id, "").data()["status"]
	good := s.login(id, "jane", "right")

	if bad.Code != http.StatusOK || !strings.Contains(bad.Body.String(), "Invalid") {
		t.Errorf("bad login: %d %s", bad.Code, bad.Body)
	}
	if status != "PENDING" {
		t.Errorf("status after a bad login = %v", status)
	}
	if good.Code != http.StatusSeeOther || mustParse(t, good.location()).Query().Get("status") != "SUCCESS" {
		t.Errorf("retry: %d %s", good.Code, good.location())
	}
}

func TestMissingCredentialsAreAskedForAgain(t *testing.T) {
	s := newServer(t)
	id := s.createPayment()

	noID := s.login(id, "", "pw")
	noPassword := s.login(id, "jane", "")
	noForm := s.do(http.MethodPost, "/bank/"+id+"/login", "")

	for name, res := range map[string]response{"no id": noID, "no password": noPassword, "no form": noForm} {
		if res.Code != http.StatusOK || !strings.Contains(res.Body.String(), `name="password"`) {
			t.Errorf("%s: %d", name, res.Code)
		}
	}
	if s.do(http.MethodGet, "/api/v1/payments/"+id, "").data()["status"] != "PENDING" {
		t.Error("the payment must still be pending")
	}
}

func TestCancel(t *testing.T) {
	s := newServer(t)
	id := s.createPayment()

	res := s.postForm("/bank/"+id+"/login", url.Values{"action": {"cancel"}})

	if res.Code != http.StatusSeeOther || mustParse(t, res.location()).Query().Get("status") != "CANCELLED" {
		t.Errorf("%d %s", res.Code, res.location())
	}
	got := s.do(http.MethodGet, "/api/v1/payments/"+id, "").data()
	if got["status"] != "CANCELLED" || got["failure_reason"] != "Cancelled by customer" {
		t.Errorf("%v", got)
	}
}

func TestSubmittingTwiceKeepsTheFirstOutcome(t *testing.T) {
	s := newServer(t)
	id := s.createPayment()
	s.login(id, "jane", "secret")

	again := s.login(id, "declined", "secret")
	cancel := s.postForm("/bank/"+id+"/login", url.Values{"action": {"cancel"}})

	for name, res := range map[string]response{"login": again, "cancel": cancel} {
		if res.Code != http.StatusSeeOther || mustParse(t, res.location()).Query().Get("status") != "SUCCESS" {
			t.Errorf("%s: %d %s", name, res.Code, res.location())
		}
	}
}

func TestVisitingAFinishedPaymentShowsAClosedPage(t *testing.T) {
	s := newServer(t)
	id := s.createPayment()
	s.login(id, "declined", "secret")

	res := s.do(http.MethodGet, "/bank/"+id, "")

	page := res.Body.String()
	if res.Code != http.StatusOK || !strings.Contains(page, "Payment failed") || strings.Contains(page, `type="password"`) {
		t.Errorf("%d %s", res.Code, page)
	}
	if !strings.Contains(page, "status=FAILED") {
		t.Error("the closed page should link back to the merchant")
	}
}

func TestACustomerCannotPayAfterTheSessionExpires(t *testing.T) {
	s := newServer(t)
	id := s.createPayment()
	s.clock.Advance(16 * time.Minute)

	page := s.do(http.MethodGet, "/bank/"+id, "")
	login := s.login(id, "jane", "secret")
	api := s.do(http.MethodGet, "/api/v1/payments/"+id, "").data()

	if !strings.Contains(page.Body.String(), "Session expired") || strings.Contains(page.Body.String(), `type="password"`) {
		t.Errorf("page: %s", page.Body)
	}
	if mustParse(t, login.location()).Query().Get("status") != "EXPIRED" {
		t.Errorf("login redirected to %s", login.location())
	}
	if api["status"] != "EXPIRED" || api["failure_reason"] != "Payment session expired" {
		t.Errorf("api: %v", api)
	}
}

func TestCredentialsInTheURLAreIgnored(t *testing.T) {
	s := newServer(t)
	id := s.createPayment()

	res := s.do(http.MethodPost, "/bank/"+id+"/login?customer_id=jane&password=secret", "")

	if res.Code == http.StatusSeeOther {
		t.Error("credentials in the query string must not log the customer in")
	}
	if s.do(http.MethodGet, "/api/v1/payments/"+id, "").data()["status"] != "PENDING" {
		t.Error("the payment must still be pending")
	}
}

func TestAnOversizedFormIsRejected(t *testing.T) {
	s := newServer(t)
	id := s.createPayment()

	res := s.postForm("/bank/"+id+"/login", url.Values{"customer_id": {"jane"}, "password": {strings.Repeat("x", 100<<10)}})

	if res.Code != http.StatusRequestEntityTooLarge || !strings.HasPrefix(res.Header().Get("Content-Type"), "text/html") {
		t.Errorf("%d %s", res.Code, res.Header().Get("Content-Type"))
	}
}

func TestManyCustomersPressingPayAtOnceFinishThePaymentOnce(t *testing.T) {
	s := newServer(t)
	id := s.createPayment()
	var wg sync.WaitGroup
	start := make(chan struct{})
	for i := 0; i < 20; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			<-start
			res := s.login(id, "jane", "secret")
			if res.Code != http.StatusSeeOther || mustParse(t, res.location()).Query().Get("status") != "SUCCESS" {
				t.Errorf("%d %s", res.Code, res.location())
			}
		}()
	}
	close(start)
	wg.Wait()

	if s.do(http.MethodGet, "/api/v1/payments/"+id, "").data()["status"] != "SUCCESS" {
		t.Error("payment did not end as SUCCESS")
	}
}

// --- credentials stay out of logs and storage ---------------------------------------

func TestThePasswordIsNeverLoggedOrStored(t *testing.T) {
	const password = "Sup3rS3cretPassw0rd"
	const customer = "jane.doe.secretid"
	dbPath := filepath.Join(t.TempDir(), "nb.db")
	repo, err := repository.OpenSQLitePaymentRepository(dbPath)
	if err != nil {
		t.Fatal(err)
	}
	s := newServer(t, func(d *app.Dependencies) { d.Payments = repo })
	id := s.createPayment()

	s.login(id, customer, password)
	s.login(id, customer, password)
	if err := repo.Close(); err != nil {
		t.Fatal(err)
	}

	logs := s.logs.String()
	if logs == "" {
		t.Fatal("expected request logs")
	}
	for _, secret := range []string{password, customer} {
		if strings.Contains(logs, secret) {
			t.Errorf("logs contain %q", secret)
		}
		for _, suffix := range []string{"", "-wal", "-shm"} {
			raw, err := os.ReadFile(dbPath + suffix)
			if err != nil {
				continue
			}
			if bytes.Contains(raw, []byte(secret)) {
				t.Errorf("database file %s%s contains %q", filepath.Base(dbPath), suffix, secret)
			}
		}
	}
}

func TestLogsNeverContainTheQueryString(t *testing.T) {
	s := newServer(t)

	s.do(http.MethodGet, "/health?token=abc123secret", "")

	if strings.Contains(s.logs.String(), "abc123secret") {
		t.Error("the query string was logged")
	}
	if !strings.Contains(s.logs.String(), "path=/health") {
		t.Errorf("request not logged: %s", s.logs)
	}
}

// --- the composition root -----------------------------------------------------------

func TestAPaymentRepositoryIsRequired(t *testing.T) {
	_, err := app.NewHandler(config.Config{}, app.Dependencies{})

	if err == nil {
		t.Error("expected an error")
	}
}

func TestBankScenariosCanBeReplacedFromOutside(t *testing.T) {
	s := newServer(t, func(d *app.Dependencies) { d.Rules = []service.AuthorizationRule{} })
	id := s.createPayment()

	res := s.login(id, "declined", "wrong")

	if mustParse(t, res.location()).Query().Get("status") != "SUCCESS" {
		t.Errorf("with no rules every customer is approved, got %s", res.location())
	}
}
