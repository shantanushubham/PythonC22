package service_test

import (
	"context"
	"errors"
	"net/http"
	"strings"
	"sync"
	"testing"
	"time"

	"airpay/netbanking/internal/apperror"
	"airpay/netbanking/internal/model"
	"airpay/netbanking/internal/repository"
	"airpay/netbanking/internal/service"
	"airpay/netbanking/internal/testutil"
)

var ctx = context.Background()

// world is a set of services wired to in-memory fakes, with no HTTP and no database.
type world struct {
	repo     *testutil.MemoryPaymentRepository
	clock    *testutil.FakeClock
	payments *service.PaymentService
	query    *service.PaymentQueryService
	session  *service.BankSessionService
}

func newWorld(t *testing.T, rules ...service.AuthorizationRule) *world {
	t.Helper()
	repo := testutil.NewMemoryPaymentRepository()
	clock := testutil.NewFakeClock()
	ids := &testutil.SequentialIDs{}
	banks := service.NewBankService(repository.NewStaticBankRepository(repository.DefaultBanks(), []string{"BKID"}))
	query := service.NewPaymentQueryService(repo, clock)
	if rules == nil {
		rules = service.DefaultAuthorizationRules()
	}
	return &world{
		repo:     repo,
		clock:    clock,
		payments: service.NewPaymentService(repo, banks, query, clock, ids, 15*time.Minute),
		query:    query,
		session: service.NewBankSessionService(
			query, repo, service.NewBankAuthorizationService(rules), clock, ids),
	}
}

func validInput() service.CreatePaymentInput {
	return service.CreatePaymentInput{
		Amount:    150050,
		Currency:  "INR",
		BankCode:  "HDFC",
		ReturnURL: "https://shop.example.com/return",
		Reference: "order_1001",
	}
}

func ptr(s string) *string { return &s }

func mustCreate(t *testing.T, w *world) model.Payment {
	t.Helper()
	result, err := w.payments.Create(ctx, validInput(), nil)
	if err != nil {
		t.Fatalf("Create: %v", err)
	}
	return result.Payment
}

func asAppError(t *testing.T, err error) *apperror.Error {
	t.Helper()
	var appErr *apperror.Error
	if !errors.As(err, &appErr) {
		t.Fatalf("got %v, want an *apperror.Error", err)
	}
	return appErr
}

func fieldNames(e *apperror.Error) []string {
	var names []string
	for _, f := range e.Fields {
		names = append(names, f.Field)
	}
	return names
}

// --- PaymentService ----------------------------------------------------------------

func TestCreateStartsAPendingPayment(t *testing.T) {
	w := newWorld(t)

	result, err := w.payments.Create(ctx, validInput(), nil)
	if err != nil {
		t.Fatal(err)
	}

	p := result.Payment
	if result.Replayed {
		t.Error("a new payment must not be marked as replayed")
	}
	if p.TransactionID != "nb_test_001" || p.Status != model.StatusPending {
		t.Errorf("got %s %s", p.TransactionID, p.Status)
	}
	if p.BankCode != "HDFC" || p.BankName != "HDFC Bank" || p.Amount != 150050 || p.Currency != "INR" {
		t.Errorf("unexpected payment %+v", p)
	}
	if !p.CreatedAt.Equal(testutil.T0) || !p.ExpiresAt.Equal(testutil.T0.Add(15*time.Minute)) {
		t.Errorf("times %v / %v", p.CreatedAt, p.ExpiresAt)
	}
}

func TestCreateNormalizesTheInput(t *testing.T) {
	w := newWorld(t)
	in := validInput()
	in.BankCode = "  hdfc "
	in.Currency = ""
	in.Reference = "  order_1 "

	result, err := w.payments.Create(ctx, in, nil)
	if err != nil {
		t.Fatal(err)
	}

	p := result.Payment
	if p.BankCode != "HDFC" || p.Currency != "INR" || p.Reference != "order_1" {
		t.Errorf("got %+v", p)
	}
}

func TestCreateReportsEveryProblemAtOnce(t *testing.T) {
	w := newWorld(t)

	_, err := w.payments.Create(ctx, service.CreatePaymentInput{
		Currency: "USD", BankCode: "NOPE", ReturnURL: "ftp://x", Reference: "has space",
	}, nil)

	appErr := asAppError(t, err)
	if appErr.Status != http.StatusBadRequest {
		t.Errorf("status %d", appErr.Status)
	}
	got := strings.Join(fieldNames(appErr), ",")
	if got != "amount,currency,bank_code,return_url,reference" {
		t.Errorf("fields = %s", got)
	}
}

func TestCreateRejectsUnsafeReturnURLs(t *testing.T) {
	cases := map[string]string{
		"":                               "return_url is required",
		"javascript:alert(1)":            "return_url must be an absolute http or https URL",
		"data:text/html,<script>":        "return_url must be an absolute http or https URL",
		"ftp://files.example.com/x":      "return_url must be an absolute http or https URL",
		"//evil.example.com/path":        "return_url must be an absolute http or https URL",
		"/relative/path":                 "return_url must be an absolute http or https URL",
		"https://":                       "return_url must be an absolute http or https URL",
		"https://good.com@evil.com/path": "return_url must not contain a username or password",
		"https://x.example/" + strings.Repeat("a", 2100): "return_url is too long",
	}
	for raw, wantMessage := range cases {
		w := newWorld(t)
		in := validInput()
		in.ReturnURL = raw

		_, err := w.payments.Create(ctx, in, nil)

		appErr := asAppError(t, err)
		if len(appErr.Fields) != 1 || appErr.Fields[0].Message != wantMessage {
			t.Errorf("%q: got %+v, want %q", raw, appErr.Fields, wantMessage)
		}
	}
}

func TestCreateAcceptsHTTPAndHTTPSReturnURLs(t *testing.T) {
	for _, raw := range []string{"https://shop.example.com/r", "http://localhost:8000/return?cart=1"} {
		w := newWorld(t)
		in := validInput()
		in.ReturnURL = raw

		if _, err := w.payments.Create(ctx, in, nil); err != nil {
			t.Errorf("%s: %v", raw, err)
		}
	}
}

func TestCreateRefusesABankThatIsDown(t *testing.T) {
	w := newWorld(t)
	in := validInput()
	in.BankCode = "BKID"

	_, err := w.payments.Create(ctx, in, nil)

	appErr := asAppError(t, err)
	if appErr.Status != http.StatusServiceUnavailable || !strings.Contains(appErr.Message, "Bank of India") {
		t.Errorf("got %d %q", appErr.Status, appErr.Message)
	}
	if w.repo.Count() != 0 {
		t.Error("a payment was stored for a bank that is down")
	}
}

func TestIdempotencyKeyReplaysTheSamePayment(t *testing.T) {
	w := newWorld(t)
	first, err := w.payments.Create(ctx, validInput(), ptr("key-1"))
	if err != nil {
		t.Fatal(err)
	}

	second, err := w.payments.Create(ctx, validInput(), ptr("key-1"))

	if err != nil {
		t.Fatal(err)
	}
	if !second.Replayed || second.Payment.TransactionID != first.Payment.TransactionID {
		t.Errorf("replayed=%v id=%s", second.Replayed, second.Payment.TransactionID)
	}
	if w.repo.Count() != 1 {
		t.Errorf("%d payments stored, want 1", w.repo.Count())
	}
}

func TestReplayShowsTheCurrentState(t *testing.T) {
	w := newWorld(t)
	first, _ := w.payments.Create(ctx, validInput(), ptr("key-1"))
	if _, err := w.session.Login(ctx, first.Payment.TransactionID, "jane", "secret"); err != nil {
		t.Fatal(err)
	}

	replay, err := w.payments.Create(ctx, validInput(), ptr("key-1"))

	if err != nil || replay.Payment.Status != model.StatusSuccess {
		t.Fatalf("got %v, %v; want SUCCESS", replay.Payment.Status, err)
	}
}

func TestReplayIgnoresHowTheRequestWasWritten(t *testing.T) {
	w := newWorld(t)
	w.payments.Create(ctx, validInput(), ptr("key-1"))
	spelledDifferently := validInput()
	spelledDifferently.BankCode = " hdfc"
	spelledDifferently.Currency = ""

	result, err := w.payments.Create(ctx, spelledDifferently, ptr("key-1"))

	if err != nil || !result.Replayed {
		t.Fatalf("got %v, %v; want a replay", result.Replayed, err)
	}
}

func TestIdempotencyKeyWithADifferentRequestIsAConflict(t *testing.T) {
	w := newWorld(t)
	w.payments.Create(ctx, validInput(), ptr("key-1"))
	different := validInput()
	different.Amount = 999

	_, err := w.payments.Create(ctx, different, ptr("key-1"))

	if appErr := asAppError(t, err); appErr.Status != http.StatusConflict {
		t.Errorf("status %d, want 409", appErr.Status)
	}
}

func TestBadIdempotencyKeysAreRejected(t *testing.T) {
	for _, key := range []string{"", "   ", "has space", "semi;colon", strings.Repeat("x", 256)} {
		w := newWorld(t)

		_, err := w.payments.Create(ctx, validInput(), ptr(key))

		if appErr := asAppError(t, err); appErr.Status != http.StatusBadRequest {
			t.Errorf("%q: status %d, want 400", key, appErr.Status)
		}
	}
}

func TestPaymentsWithoutAKeyAreNeverReplayed(t *testing.T) {
	w := newWorld(t)

	a, _ := w.payments.Create(ctx, validInput(), nil)
	b, _ := w.payments.Create(ctx, validInput(), nil)

	if a.Payment.TransactionID == b.Payment.TransactionID || b.Replayed {
		t.Error("two requests with no key must be two payments")
	}
}

func TestConcurrentRequestsWithOneKeyCreateOnePayment(t *testing.T) {
	w := newWorld(t)
	var (
		wg      sync.WaitGroup
		mu      sync.Mutex
		ids     = map[string]bool{}
		created int
	)
	start := make(chan struct{})
	for i := 0; i < 25; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			<-start
			result, err := w.payments.Create(ctx, validInput(), ptr("race"))
			mu.Lock()
			defer mu.Unlock()
			if err != nil {
				t.Errorf("Create: %v", err)
				return
			}
			ids[result.Payment.TransactionID] = true
			if !result.Replayed {
				created++
			}
		}()
	}
	close(start)
	wg.Wait()

	if len(ids) != 1 || created != 1 || w.repo.Count() != 1 {
		t.Errorf("%d distinct ids, %d created, %d stored; want 1 of each", len(ids), created, w.repo.Count())
	}
}

// --- PaymentQueryService -----------------------------------------------------------

func TestGetUnknownPaymentIsNotFound(t *testing.T) {
	w := newWorld(t)

	_, err := w.query.Get(ctx, "nb_missing")

	appErr := asAppError(t, err)
	if appErr.Status != http.StatusNotFound || appErr.Message != "No payment found with id 'nb_missing'" {
		t.Errorf("got %d %q", appErr.Status, appErr.Message)
	}
}

func TestAPaymentExpiresOnlyAfterItsDeadline(t *testing.T) {
	w := newWorld(t)
	p := mustCreate(t, w)

	w.clock.Advance(15 * time.Minute) // exactly at the deadline
	atDeadline, _ := w.query.Get(ctx, p.TransactionID)
	w.clock.Advance(time.Nanosecond)
	afterDeadline, err := w.query.Get(ctx, p.TransactionID)

	if err != nil {
		t.Fatal(err)
	}
	if atDeadline.Status != model.StatusPending {
		t.Errorf("at the deadline: %s, want PENDING", atDeadline.Status)
	}
	if afterDeadline.Status != model.StatusExpired || afterDeadline.FailureReason != service.ExpiredReason {
		t.Errorf("after the deadline: %s %q", afterDeadline.Status, afterDeadline.FailureReason)
	}
	if afterDeadline.CompletedAt == nil {
		t.Error("an expired payment must record when it expired")
	}
}

func TestAFinishedPaymentNeverExpires(t *testing.T) {
	w := newWorld(t)
	p := mustCreate(t, w)
	w.session.Login(ctx, p.TransactionID, "jane", "secret")

	w.clock.Advance(48 * time.Hour)
	got, _ := w.query.Get(ctx, p.TransactionID)

	if got.Status != model.StatusSuccess {
		t.Errorf("status %s, want SUCCESS", got.Status)
	}
}

// --- BankAuthorizationService ------------------------------------------------------

func attempt(customer, password string) service.Attempt {
	return service.Attempt{BankCode: "HDFC", CustomerID: customer, Password: password, Amount: 100}
}

func TestDefaultScenarios(t *testing.T) {
	auth := service.NewBankAuthorizationService(service.DefaultAuthorizationRules())
	declines := map[string]string{
		"insufficient": "Insufficient funds",
		"declined":     "Transaction declined by bank",
		"timeout":      "Bank server timeout",
		"locked":       "Customer account is locked",
		"limit":        "Transaction limit exceeded",
		"INSUFFICIENT": "Insufficient funds",
	}
	for customer, reason := range declines {
		verdict := auth.Authorize(attempt(customer, "pw"))
		if verdict.Kind != service.VerdictDecline || verdict.Reason != reason {
			t.Errorf("%s: got %+v, want decline %q", customer, verdict, reason)
		}
	}

	if v := auth.Authorize(attempt("anyone", "pw")); v.Kind != service.VerdictApprove {
		t.Errorf("an ordinary customer got %+v, want approve", v)
	}
	if v := auth.Authorize(attempt("anyone", "wrong")); v.Kind != service.VerdictInvalidCredentials {
		t.Errorf("password 'wrong' got %+v, want invalid credentials", v)
	}
}

func TestWrongPasswordIsCheckedBeforeScenarios(t *testing.T) {
	auth := service.NewBankAuthorizationService(service.DefaultAuthorizationRules())

	verdict := auth.Authorize(attempt("insufficient", "wrong"))

	if verdict.Kind != service.VerdictInvalidCredentials {
		t.Errorf("got %+v; the login failure must come first", verdict)
	}
}

// largeAmountRule is a scenario the service does not know about.
type largeAmountRule struct{}

func (largeAmountRule) Evaluate(a service.Attempt) (service.Verdict, bool) {
	if a.Amount > 500000 {
		return service.Verdict{Kind: service.VerdictDecline, Reason: "Amount over limit"}, true
	}
	return service.Verdict{}, false
}

func TestANewScenarioIsAddedAsARule(t *testing.T) {
	rules := append(service.DefaultAuthorizationRules(), largeAmountRule{})
	auth := service.NewBankAuthorizationService(rules)

	small := auth.Authorize(service.Attempt{CustomerID: "jane", Password: "pw", Amount: 100})
	large := auth.Authorize(service.Attempt{CustomerID: "jane", Password: "pw", Amount: 600000})

	if small.Kind != service.VerdictApprove {
		t.Errorf("small amount: %+v", small)
	}
	if large.Kind != service.VerdictDecline || large.Reason != "Amount over limit" {
		t.Errorf("large amount: %+v", large)
	}
}

func TestABankWithNoRulesApprovesEveryone(t *testing.T) {
	auth := service.NewBankAuthorizationService(nil)

	if v := auth.Authorize(attempt("insufficient", "wrong")); v.Kind != service.VerdictApprove {
		t.Errorf("got %+v", v)
	}
}

func TestAnAttemptNeverPrintsThePassword(t *testing.T) {
	text := attempt("jane", "S3cretPassw0rd!").String()

	if strings.Contains(text, "S3cretPassw0rd!") || !strings.Contains(text, "redacted") {
		t.Errorf("String() = %s", text)
	}
}

// --- BankSessionService ------------------------------------------------------------

func TestLoginApprovesAnOrdinaryCustomer(t *testing.T) {
	w := newWorld(t)
	p := mustCreate(t, w)

	result, err := w.session.Login(ctx, p.TransactionID, "jane", "secret")

	if err != nil {
		t.Fatal(err)
	}
	got := result.Payment
	if got.Status != model.StatusSuccess || !strings.HasPrefix(got.BankReference, "HDFC") || got.CompletedAt == nil {
		t.Errorf("got %+v", got)
	}
}

func TestLoginDeclineIsFinalAndCarriesTheReason(t *testing.T) {
	w := newWorld(t)
	p := mustCreate(t, w)

	result, _ := w.session.Login(ctx, p.TransactionID, "insufficient", "secret")

	if result.Payment.Status != model.StatusFailed || result.Payment.FailureReason != "Insufficient funds" {
		t.Errorf("got %+v", result.Payment)
	}
	if result.Payment.BankReference != "" {
		t.Error("a failed payment must have no bank reference")
	}
}

func TestBadLoginLeavesThePaymentPendingForARetry(t *testing.T) {
	w := newWorld(t)
	p := mustCreate(t, w)

	bad, _ := w.session.Login(ctx, p.TransactionID, "jane", "wrong")
	retry, _ := w.session.Login(ctx, p.TransactionID, "jane", "right")

	if bad.RetryMessage == "" || bad.Payment.Status != model.StatusPending {
		t.Errorf("after a bad login: %+v", bad)
	}
	if retry.RetryMessage != "" || retry.Payment.Status != model.StatusSuccess {
		t.Errorf("after the retry: %+v", retry)
	}
}

func TestMissingCredentialsAskTheCustomerToRetry(t *testing.T) {
	cases := []struct{ customer, password, message string }{
		{"", "pw", "Enter your customer ID."},
		{"   ", "pw", "Enter your customer ID."},
		{"jane", "", "Enter your password."},
		{strings.Repeat("a", 65), "pw", "Customer ID is too long."},
		{"jane", strings.Repeat("a", 129), "Password is too long."},
	}
	for _, c := range cases {
		w := newWorld(t)
		p := mustCreate(t, w)

		result, err := w.session.Login(ctx, p.TransactionID, c.customer, c.password)

		if err != nil || result.RetryMessage != c.message || result.Payment.Status != model.StatusPending {
			t.Errorf("%q/%q: got %+v, %v; want retry %q", c.customer, c.password, result, err, c.message)
		}
	}
}

func TestLoginOnAFinishedPaymentChangesNothing(t *testing.T) {
	w := newWorld(t)
	p := mustCreate(t, w)
	first, _ := w.session.Login(ctx, p.TransactionID, "jane", "secret")

	again, err := w.session.Login(ctx, p.TransactionID, "insufficient", "secret")

	if err != nil || again.Payment.Status != model.StatusSuccess ||
		again.Payment.BankReference != first.Payment.BankReference {
		t.Errorf("got %+v, %v; the finished payment must not change", again.Payment, err)
	}
}

func TestLoginOnAnExpiredPaymentReportsExpiry(t *testing.T) {
	w := newWorld(t)
	p := mustCreate(t, w)
	w.clock.Advance(16 * time.Minute)

	result, _ := w.session.Login(ctx, p.TransactionID, "jane", "secret")

	if result.Payment.Status != model.StatusExpired {
		t.Errorf("status %s, want EXPIRED; an expired payment must not be payable", result.Payment.Status)
	}
}

func TestLoginOnAnUnknownPaymentIsNotFound(t *testing.T) {
	w := newWorld(t)

	_, err := w.session.Login(ctx, "nb_missing", "jane", "secret")

	if appErr := asAppError(t, err); appErr.Status != http.StatusNotFound {
		t.Errorf("status %d", appErr.Status)
	}
}

func TestCancel(t *testing.T) {
	w := newWorld(t)
	p := mustCreate(t, w)

	got, err := w.session.Cancel(ctx, p.TransactionID)

	if err != nil || got.Status != model.StatusCancelled || got.FailureReason != "Cancelled by customer" {
		t.Fatalf("got %+v, %v", got, err)
	}
	again, _ := w.session.Cancel(ctx, p.TransactionID)
	if again.Status != model.StatusCancelled {
		t.Errorf("cancelling twice changed the status to %s", again.Status)
	}
}

func TestCancelCannotUndoASuccessfulPayment(t *testing.T) {
	w := newWorld(t)
	p := mustCreate(t, w)
	w.session.Login(ctx, p.TransactionID, "jane", "secret")

	got, _ := w.session.Cancel(ctx, p.TransactionID)

	if got.Status != model.StatusSuccess {
		t.Errorf("status %s, want SUCCESS", got.Status)
	}
}

// losesTheRace finishes the payment itself, as a second browser tab would, just before
// the caller's own Complete runs. The caller's Complete then reports ErrNotPending.
type losesTheRace struct {
	repository.PaymentRepository
	rival model.Completion
}

func (r *losesTheRace) Complete(c context.Context, id string, mine model.Completion) (model.Payment, error) {
	_, _ = r.PaymentRepository.Complete(c, id, r.rival)
	return r.PaymentRepository.Complete(c, id, mine)
}

func TestWhenAnotherRequestFinishesFirstItsOutcomeWins(t *testing.T) {
	w := newWorld(t)
	p := mustCreate(t, w)
	rival := model.Completion{Status: model.StatusCancelled, FailureReason: "Cancelled by customer", At: testutil.T0}
	racing := &losesTheRace{PaymentRepository: w.repo, rival: rival}
	session := service.NewBankSessionService(
		w.query, racing,
		service.NewBankAuthorizationService(service.DefaultAuthorizationRules()),
		w.clock, &testutil.SequentialIDs{})

	result, err := session.Login(ctx, p.TransactionID, "jane", "secret")

	if err != nil {
		t.Fatal(err)
	}
	if result.Payment.Status != model.StatusCancelled {
		t.Errorf("status %s, want the rival's CANCELLED", result.Payment.Status)
	}
}

func TestManyCustomersPressingPayAtOnceFinishThePaymentOnce(t *testing.T) {
	w := newWorld(t)
	p := mustCreate(t, w)
	var (
		wg   sync.WaitGroup
		mu   sync.Mutex
		refs = map[string]bool{}
	)
	start := make(chan struct{})
	for i := 0; i < 25; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			<-start
			result, err := w.session.Login(ctx, p.TransactionID, "jane", "secret")
			mu.Lock()
			defer mu.Unlock()
			if err != nil || result.Payment.Status != model.StatusSuccess {
				t.Errorf("got %+v, %v", result.Payment, err)
				return
			}
			refs[result.Payment.BankReference] = true
		}()
	}
	close(start)
	wg.Wait()

	if len(refs) != 1 {
		t.Errorf("%d different bank references, want 1: the payment was completed more than once", len(refs))
	}
}

func TestIDsAreUniqueAndWellFormed(t *testing.T) {
	ids := service.RandomIDs{}
	seen := map[string]bool{}
	for i := 0; i < 1000; i++ {
		id := ids.TransactionID()
		if !strings.HasPrefix(id, "nb_") || len(id) != len("nb_")+36 || seen[id] {
			t.Fatalf("bad or repeated id %q", id)
		}
		seen[id] = true
	}

	ref := ids.BankReference("HDFC")
	if len(ref) != len("HDFC")+12 || !strings.HasPrefix(ref, "HDFC") {
		t.Errorf("bank reference %q", ref)
	}
}

func TestListBanksCanFilterByStatus(t *testing.T) {
	banks := service.NewBankService(repository.NewStaticBankRepository(repository.DefaultBanks(), []string{"BKID", "SBIN"}))
	down, up := model.BankDown, model.BankUp

	if got := banks.List(&down); len(got) != 2 {
		t.Errorf("%d banks down, want 2", len(got))
	}
	if got := banks.List(&up); len(got) != len(repository.DefaultBanks())-2 {
		t.Errorf("%d banks up", len(got))
	}
	if got := banks.List(nil); len(got) != len(repository.DefaultBanks()) {
		t.Errorf("%d banks in total", len(got))
	}
}
