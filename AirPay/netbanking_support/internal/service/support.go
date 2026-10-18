// Package service holds the business rules.
//
// Each service does one job and receives what it needs through its constructor, as
// small interfaces (Dependency Inversion). Nothing here knows about HTTP or SQL.
package service

import (
	"crypto/rand"
	"fmt"
	"math/big"
	"time"
)

// Clock tells the time. Tests replace it to control expiry.
type Clock interface {
	Now() time.Time
}

// SystemClock is the real clock, in UTC.
type SystemClock struct{}

func (SystemClock) Now() time.Time { return time.Now().UTC() }

// IDGenerator makes the ids the service hands out.
type IDGenerator interface {
	// TransactionID returns a new unique id for a payment, such as "nb_<uuid>".
	TransactionID() string
	// BankReference returns the reference the bank gives a successful payment.
	BankReference(bankCode string) string
}

// RandomIDs generates ids from the system's secure random source.
type RandomIDs struct{}

func (RandomIDs) TransactionID() string {
	var b [16]byte
	_, _ = rand.Read(b[:])
	b[6] = (b[6] & 0x0f) | 0x40 // version 4
	b[8] = (b[8] & 0x3f) | 0x80 // RFC 4122 variant
	return fmt.Sprintf("nb_%x-%x-%x-%x-%x", b[0:4], b[4:6], b[6:8], b[8:10], b[10:])
}

func (RandomIDs) BankReference(bankCode string) string {
	n, _ := rand.Int(rand.Reader, big.NewInt(1_000_000_000_000))
	return fmt.Sprintf("%s%012d", bankCode, n.Int64())
}
