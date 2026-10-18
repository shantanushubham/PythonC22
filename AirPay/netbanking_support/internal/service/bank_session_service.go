package service

import (
	"context"
	"errors"
	"strings"

	"airpay/netbanking/internal/model"
	"airpay/netbanking/internal/repository"
)

const (
	cancelledReason = "Cancelled by customer"
	maxCustomerID   = 64
	maxPassword     = 128
)

// LoginResult is what happened when the customer pressed "Pay".
type LoginResult struct {
	Payment model.Payment
	// RetryMessage is set when the customer should try again, for example after a bad
	// password. The payment is still PENDING in that case.
	RetryMessage string
}

// BankSessionService is the customer's visit to the bank's page.
//
// It never stores or logs the password. The password is used only to ask the
// authorization service for a verdict.
type BankSessionService struct {
	query    *PaymentQueryService
	payments repository.PaymentWriter
	auth     *BankAuthorizationService
	clock    Clock
	ids      IDGenerator
}

func NewBankSessionService(
	query *PaymentQueryService,
	payments repository.PaymentWriter,
	auth *BankAuthorizationService,
	clock Clock,
	ids IDGenerator,
) *BankSessionService {
	return &BankSessionService{query: query, payments: payments, auth: auth, clock: clock, ids: ids}
}

// Open returns the payment the customer is about to pay.
func (s *BankSessionService) Open(ctx context.Context, transactionID string) (model.Payment, error) {
	return s.query.Get(ctx, transactionID)
}

// Login handles the customer pressing "Pay". A payment that is already final is
// returned untouched, so a double click or a stale tab does no harm.
func (s *BankSessionService) Login(ctx context.Context, transactionID, customerID, password string) (LoginResult, error) {
	payment, err := s.query.Get(ctx, transactionID)
	if err != nil {
		return LoginResult{}, err
	}
	if payment.Status.Final() {
		return LoginResult{Payment: payment}, nil
	}

	customerID = strings.TrimSpace(customerID)
	if message := checkCredentials(customerID, password); message != "" {
		return LoginResult{Payment: payment, RetryMessage: message}, nil
	}

	verdict := s.auth.Authorize(Attempt{
		BankCode:   payment.BankCode,
		CustomerID: customerID,
		Password:   password,
		Amount:     payment.Amount,
	})

	switch verdict.Kind {
	case VerdictInvalidCredentials:
		return LoginResult{Payment: payment, RetryMessage: "Invalid customer ID or password."}, nil
	case VerdictDecline:
		return s.finish(ctx, payment, model.Completion{
			Status:        model.StatusFailed,
			FailureReason: verdict.Reason,
			At:            s.clock.Now(),
		})
	default:
		return s.finish(ctx, payment, model.Completion{
			Status:        model.StatusSuccess,
			BankReference: s.ids.BankReference(payment.BankCode),
			At:            s.clock.Now(),
		})
	}
}

// Cancel handles the customer pressing "Cancel".
func (s *BankSessionService) Cancel(ctx context.Context, transactionID string) (model.Payment, error) {
	payment, err := s.query.Get(ctx, transactionID)
	if err != nil {
		return model.Payment{}, err
	}
	if payment.Status.Final() {
		return payment, nil
	}
	result, err := s.finish(ctx, payment, model.Completion{
		Status:        model.StatusCancelled,
		FailureReason: cancelledReason,
		At:            s.clock.Now(),
	})
	return result.Payment, err
}

// finish moves the payment to a final state. If another request got there first, it
// returns that request's outcome instead.
func (s *BankSessionService) finish(ctx context.Context, payment model.Payment, c model.Completion) (LoginResult, error) {
	done, err := s.payments.Complete(ctx, payment.TransactionID, c)
	if errors.Is(err, repository.ErrNotPending) {
		current, getErr := s.query.Get(ctx, payment.TransactionID)
		return LoginResult{Payment: current}, getErr
	}
	if err != nil {
		return LoginResult{}, err
	}
	return LoginResult{Payment: done}, nil
}

func checkCredentials(customerID, password string) string {
	switch {
	case customerID == "":
		return "Enter your customer ID."
	case len(customerID) > maxCustomerID:
		return "Customer ID is too long."
	case password == "":
		return "Enter your password."
	case len(password) > maxPassword:
		return "Password is too long."
	}
	return ""
}
