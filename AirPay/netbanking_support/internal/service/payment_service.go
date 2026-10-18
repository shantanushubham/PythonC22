package service

import (
	"context"
	"errors"
	"fmt"
	"net/url"
	"regexp"
	"strings"
	"time"

	"airpay/netbanking/internal/apperror"
	"airpay/netbanking/internal/model"
	"airpay/netbanking/internal/repository"
)

var referencePattern = regexp.MustCompile(`^[A-Za-z0-9_-]{1,64}$`)

const maxReturnURLLength = 2048

// CreatePaymentInput is what a caller asks for.
type CreatePaymentInput struct {
	Amount    model.Amount
	Currency  string
	BankCode  string
	ReturnURL string
	Reference string
}

// CreateResult is the outcome of Create.
type CreateResult struct {
	Payment  model.Payment
	Replayed bool // true when this is the stored result of an earlier identical request
}

// PaymentService starts netbanking payments.
//
// It makes the decisions about a new payment (is the request valid, is the bank up, is
// this a retry) and leaves the rest to the classes it is given.
type PaymentService struct {
	payments    repository.PaymentRepository
	banks       *BankService
	query       *PaymentQueryService
	idempotency IdempotencyService
	clock       Clock
	ids         IDGenerator
	ttl         time.Duration
}

func NewPaymentService(
	payments repository.PaymentRepository,
	banks *BankService,
	query *PaymentQueryService,
	clock Clock,
	ids IDGenerator,
	ttl time.Duration,
) *PaymentService {
	return &PaymentService{
		payments: payments,
		banks:    banks,
		query:    query,
		clock:    clock,
		ids:      ids,
		ttl:      ttl,
	}
}

// Create starts a payment in the PENDING state. rawKey is the Idempotency-Key header,
// or nil if it was not sent.
func (s *PaymentService) Create(ctx context.Context, input CreatePaymentInput, rawKey *string) (CreateResult, error) {
	key, err := s.idempotency.CleanKey(rawKey)
	if err != nil {
		return CreateResult{}, err
	}

	input = normalize(input)
	fingerprint := s.idempotency.Fingerprint(input)

	// Fast path: this key was already used, so replay without validating again.
	if key != "" {
		stored, err := s.payments.GetByIdempotencyKey(ctx, key)
		if err == nil {
			return s.replay(ctx, stored, fingerprint)
		}
		if !errors.Is(err, repository.ErrNotFound) {
			return CreateResult{}, err
		}
	}

	bank, fields := s.validate(input)
	if len(fields) > 0 {
		return CreateResult{}, apperror.Validation(fields...)
	}
	if bank.Status != model.BankUp {
		return CreateResult{}, apperror.Unavailable(
			fmt.Sprintf("%s is currently unavailable. Try another bank or retry later.", bank.Name))
	}

	now := s.clock.Now()
	payment := model.Payment{
		TransactionID: s.ids.TransactionID(),
		Status:        model.StatusPending,
		Amount:        input.Amount,
		Currency:      input.Currency,
		BankCode:      bank.Code,
		BankName:      bank.Name,
		ReturnURL:     input.ReturnURL,
		Reference:     input.Reference,
		CreatedAt:     now,
		ExpiresAt:     now.Add(s.ttl),
	}

	err = s.payments.Create(ctx, repository.StoredPayment{
		Payment:        payment,
		Fingerprint:    fingerprint,
		IdempotencyKey: key,
	})
	if errors.Is(err, repository.ErrDuplicateIdempotencyKey) {
		// Another request saved this key between our check and our save. The
		// repository picked the winner, so replay it.
		winner, getErr := s.payments.GetByIdempotencyKey(ctx, key)
		if getErr != nil {
			return CreateResult{}, getErr
		}
		return s.replay(ctx, winner, fingerprint)
	}
	if err != nil {
		return CreateResult{}, err
	}
	return CreateResult{Payment: payment}, nil
}

// replay returns the payment an earlier identical request created, in its current state.
func (s *PaymentService) replay(ctx context.Context, stored repository.StoredPayment, fingerprint string) (CreateResult, error) {
	if err := s.idempotency.EnsureSameRequest(stored, fingerprint); err != nil {
		return CreateResult{}, err
	}
	current, err := s.query.Get(ctx, stored.Payment.TransactionID)
	if err != nil {
		return CreateResult{}, err
	}
	return CreateResult{Payment: current, Replayed: true}, nil
}

func normalize(in CreatePaymentInput) CreatePaymentInput {
	in.Currency = strings.ToUpper(strings.TrimSpace(in.Currency))
	if in.Currency == "" {
		in.Currency = "INR"
	}
	in.BankCode = strings.ToUpper(strings.TrimSpace(in.BankCode))
	in.ReturnURL = strings.TrimSpace(in.ReturnURL)
	in.Reference = strings.TrimSpace(in.Reference)
	return in
}

// validate checks every field and reports all the problems at once.
func (s *PaymentService) validate(in CreatePaymentInput) (model.Bank, []apperror.FieldError) {
	var fields []apperror.FieldError

	if in.Amount == 0 {
		fields = append(fields, apperror.Field("amount", "amount is required"))
	}
	if in.Currency != "INR" {
		fields = append(fields, apperror.Field("currency", `currency must be "INR"`))
	}

	var bank model.Bank
	if in.BankCode == "" {
		fields = append(fields, apperror.Field("bank_code", "bank_code is required"))
	} else if found, ok := s.banks.Find(in.BankCode); !ok {
		fields = append(fields, apperror.Field("bank_code", "bank_code is not a supported bank"))
	} else {
		bank = found
	}

	if message := checkReturnURL(in.ReturnURL); message != "" {
		fields = append(fields, apperror.Field("return_url", message))
	}
	if in.Reference != "" && !referencePattern.MatchString(in.Reference) {
		fields = append(fields,
			apperror.Field("reference", "reference must be 1-64 characters: letters, digits, _ and -"))
	}
	return bank, fields
}

// checkReturnURL returns a problem with the URL, or "" if it is acceptable. Only
// absolute http and https URLs are allowed, so a "javascript:" or "data:" URL can never
// become a redirect target. Credentials in the URL are refused because they disguise
// the real host.
func checkReturnURL(raw string) string {
	if raw == "" {
		return "return_url is required"
	}
	if len(raw) > maxReturnURLLength {
		return "return_url is too long"
	}
	u, err := url.Parse(raw)
	if err != nil || u.Host == "" || (u.Scheme != "http" && u.Scheme != "https") {
		return "return_url must be an absolute http or https URL"
	}
	if u.User != nil {
		return "return_url must not contain a username or password"
	}
	return ""
}
