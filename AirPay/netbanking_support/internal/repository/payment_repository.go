// Package repository saves and loads payments and banks.
//
// Services depend on the interfaces here, never on a database. Any implementation
// must follow the contract documented below so one can replace another without the
// services noticing (Liskov Substitution). The checks in package repotest run against
// every implementation.
//
// Interface Segregation: reading and writing are separate interfaces. Code that only
// looks payments up asks for a PaymentReader and cannot change anything.
package repository

import (
	"context"
	"errors"

	"airpay/netbanking/internal/model"
)

var (
	// ErrNotFound means no payment has the id or idempotency key that was asked for.
	ErrNotFound = errors.New("payment not found")
	// ErrDuplicatePayment means a payment with this transaction id already exists.
	ErrDuplicatePayment = errors.New("payment already exists")
	// ErrDuplicateIdempotencyKey means a payment with this idempotency key already exists.
	ErrDuplicateIdempotencyKey = errors.New("idempotency key already used")
	// ErrNotPending means the payment already reached a final state.
	ErrNotPending = errors.New("payment is not pending")
)

// StoredPayment is a payment plus what is needed to recognise a retried request.
type StoredPayment struct {
	Payment        model.Payment
	Fingerprint    string
	IdempotencyKey string // empty when the caller sent no key
}

// PaymentReader looks payments up.
type PaymentReader interface {
	// Get returns the payment, or ErrNotFound.
	Get(ctx context.Context, transactionID string) (StoredPayment, error)
	// GetByIdempotencyKey returns the payment saved under the key, or ErrNotFound.
	GetByIdempotencyKey(ctx context.Context, key string) (StoredPayment, error)
}

// PaymentWriter creates payments and moves them to a final state.
type PaymentWriter interface {
	// Create stores a new payment. It returns ErrDuplicateIdempotencyKey if the key is
	// taken and ErrDuplicatePayment if the transaction id is. A rejected payment is not
	// stored. Payments with no key never collide with each other. The key check is
	// atomic: of several concurrent Creates with one key, exactly one succeeds.
	Create(ctx context.Context, payment StoredPayment) error

	// Complete moves a PENDING payment to a final state and returns it. It returns
	// ErrNotFound for an unknown id and ErrNotPending, leaving the payment unchanged, if
	// it already reached a final state. This is atomic: of several concurrent Completes
	// of one payment, exactly one succeeds.
	Complete(ctx context.Context, transactionID string, completion model.Completion) (model.Payment, error)
}

// PaymentRepository is everything a service that creates and finishes payments needs.
type PaymentRepository interface {
	PaymentReader
	PaymentWriter
}
