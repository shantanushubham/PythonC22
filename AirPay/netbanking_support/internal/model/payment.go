// Package model holds the data the services and repositories pass around.
package model

import "time"

// PaymentStatus is where a netbanking payment is in its life.
//
//	PENDING -> SUCCESS | FAILED | CANCELLED | EXPIRED
//
// PENDING is the only state that can change. Every other state is final.
type PaymentStatus string

const (
	StatusPending   PaymentStatus = "PENDING"
	StatusSuccess   PaymentStatus = "SUCCESS"
	StatusFailed    PaymentStatus = "FAILED"
	StatusCancelled PaymentStatus = "CANCELLED"
	StatusExpired   PaymentStatus = "EXPIRED"
)

// Final reports whether the payment can no longer change.
func (s PaymentStatus) Final() bool { return s != StatusPending }

// Payment is one netbanking payment. It never holds customer credentials.
type Payment struct {
	TransactionID string
	Status        PaymentStatus
	Amount        Amount
	Currency      string
	BankCode      string
	BankName      string
	ReturnURL     string
	Reference     string
	BankReference string
	FailureReason string
	CreatedAt     time.Time
	ExpiresAt     time.Time
	CompletedAt   *time.Time
}

// Completion moves a PENDING payment to a final state.
type Completion struct {
	Status        PaymentStatus
	FailureReason string
	BankReference string
	At            time.Time
}
