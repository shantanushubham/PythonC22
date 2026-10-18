package service

import (
	"context"
	"errors"
	"fmt"

	"airpay/netbanking/internal/apperror"
	"airpay/netbanking/internal/model"
	"airpay/netbanking/internal/repository"
)

// ExpiredReason is the failure reason given to a payment nobody completed in time.
const ExpiredReason = "Payment session expired"

// PaymentQueryService reads payments.
//
// Nothing runs in the background, so a payment past its deadline is moved to EXPIRED
// the first time it is read. Every reader therefore sees the same, current state.
type PaymentQueryService struct {
	payments repository.PaymentRepository
	clock    Clock
}

func NewPaymentQueryService(payments repository.PaymentRepository, clock Clock) *PaymentQueryService {
	return &PaymentQueryService{payments: payments, clock: clock}
}

// Get returns the payment, or a 404 error.
func (s *PaymentQueryService) Get(ctx context.Context, transactionID string) (model.Payment, error) {
	stored, err := s.payments.Get(ctx, transactionID)
	if errors.Is(err, repository.ErrNotFound) {
		return model.Payment{}, apperror.NotFound(fmt.Sprintf("No payment found with id '%s'", transactionID))
	}
	if err != nil {
		return model.Payment{}, err
	}
	return s.expireIfDue(ctx, stored.Payment)
}

func (s *PaymentQueryService) expireIfDue(ctx context.Context, p model.Payment) (model.Payment, error) {
	now := s.clock.Now()
	if p.Status != model.StatusPending || !now.After(p.ExpiresAt) {
		return p, nil
	}

	expired, err := s.payments.Complete(ctx, p.TransactionID, model.Completion{
		Status:        model.StatusExpired,
		FailureReason: ExpiredReason,
		At:            now,
	})
	if errors.Is(err, repository.ErrNotPending) {
		// Someone finished it between our read and our update. Report what they did.
		stored, getErr := s.payments.Get(ctx, p.TransactionID)
		return stored.Payment, getErr
	}
	return expired, err
}
