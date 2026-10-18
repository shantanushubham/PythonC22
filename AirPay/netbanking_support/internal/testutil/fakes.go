// Package testutil holds test doubles. It is imported by tests only.
package testutil

import (
	"context"
	"fmt"
	"sync"
	"time"

	"airpay/netbanking/internal/model"
	"airpay/netbanking/internal/repository"
)

// T0 is the instant every fake clock starts at.
var T0 = time.Date(2026, 10, 18, 12, 0, 0, 0, time.UTC)

// FakeClock is a clock tests can move.
type FakeClock struct {
	mu  sync.Mutex
	now time.Time
}

func NewFakeClock() *FakeClock { return &FakeClock{now: T0} }

func (c *FakeClock) Now() time.Time {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.now
}

func (c *FakeClock) Advance(d time.Duration) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.now = c.now.Add(d)
}

// SequentialIDs hands out predictable ids: nb_test_001, nb_test_002, ...
type SequentialIDs struct {
	mu sync.Mutex
	n  int
}

func (s *SequentialIDs) TransactionID() string {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.n++
	return fmt.Sprintf("nb_test_%03d", s.n)
}

func (s *SequentialIDs) BankReference(bankCode string) string {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.n++
	return fmt.Sprintf("%s%012d", bankCode, s.n)
}

// MemoryPaymentRepository is a second implementation of the repository contract. It
// exists to prove the services work with any repository, and to keep unit tests fast.
type MemoryPaymentRepository struct {
	mu    sync.Mutex
	byID  map[string]repository.StoredPayment
	byKey map[string]string
}

var _ repository.PaymentRepository = (*MemoryPaymentRepository)(nil)

func NewMemoryPaymentRepository() *MemoryPaymentRepository {
	return &MemoryPaymentRepository{
		byID:  map[string]repository.StoredPayment{},
		byKey: map[string]string{},
	}
}

func (r *MemoryPaymentRepository) Create(_ context.Context, sp repository.StoredPayment) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	if sp.IdempotencyKey != "" {
		if _, taken := r.byKey[sp.IdempotencyKey]; taken {
			return repository.ErrDuplicateIdempotencyKey
		}
	}
	if _, taken := r.byID[sp.Payment.TransactionID]; taken {
		return repository.ErrDuplicatePayment
	}
	r.byID[sp.Payment.TransactionID] = sp
	if sp.IdempotencyKey != "" {
		r.byKey[sp.IdempotencyKey] = sp.Payment.TransactionID
	}
	return nil
}

func (r *MemoryPaymentRepository) Get(_ context.Context, id string) (repository.StoredPayment, error) {
	r.mu.Lock()
	defer r.mu.Unlock()
	sp, ok := r.byID[id]
	if !ok {
		return repository.StoredPayment{}, repository.ErrNotFound
	}
	return sp, nil
}

func (r *MemoryPaymentRepository) GetByIdempotencyKey(_ context.Context, key string) (repository.StoredPayment, error) {
	r.mu.Lock()
	defer r.mu.Unlock()
	id, ok := r.byKey[key]
	if !ok {
		return repository.StoredPayment{}, repository.ErrNotFound
	}
	return r.byID[id], nil
}

func (r *MemoryPaymentRepository) Complete(_ context.Context, id string, c model.Completion) (model.Payment, error) {
	r.mu.Lock()
	defer r.mu.Unlock()

	sp, ok := r.byID[id]
	if !ok {
		return model.Payment{}, repository.ErrNotFound
	}
	if sp.Payment.Status != model.StatusPending {
		return model.Payment{}, repository.ErrNotPending
	}
	at := c.At
	sp.Payment.Status = c.Status
	sp.Payment.FailureReason = c.FailureReason
	sp.Payment.BankReference = c.BankReference
	sp.Payment.CompletedAt = &at
	r.byID[id] = sp
	return sp.Payment, nil
}

// Count is how many payments are stored.
func (r *MemoryPaymentRepository) Count() int {
	r.mu.Lock()
	defer r.mu.Unlock()
	return len(r.byID)
}
