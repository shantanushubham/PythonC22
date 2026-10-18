package service

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"regexp"
	"strings"

	"airpay/netbanking/internal/apperror"
	"airpay/netbanking/internal/repository"
)

var idempotencyKeyPattern = regexp.MustCompile(`^[A-Za-z0-9._:-]{1,255}$`)

// IdempotencyService holds the rules for the Idempotency-Key header.
type IdempotencyService struct{}

// CleanKey returns the trimmed key, or "" when the header was not sent (raw is nil).
func (IdempotencyService) CleanKey(raw *string) (string, error) {
	if raw == nil {
		return "", nil
	}
	key := strings.TrimSpace(*raw)
	if !idempotencyKeyPattern.MatchString(key) {
		return "", apperror.BadRequest(
			"Idempotency-Key must be 1-255 characters and use only letters, digits, and . _ : -")
	}
	return key, nil
}

// Fingerprint hashes the request, so a retry can be told apart from a different request
// that reuses the same key.
func (IdempotencyService) Fingerprint(input CreatePaymentInput) string {
	raw, _ := json.Marshal(struct {
		Amount    int64  `json:"amount"`
		Currency  string `json:"currency"`
		BankCode  string `json:"bank_code"`
		ReturnURL string `json:"return_url"`
		Reference string `json:"reference"`
	}{int64(input.Amount), input.Currency, input.BankCode, input.ReturnURL, input.Reference})
	sum := sha256.Sum256(raw)
	return hex.EncodeToString(sum[:])
}

// EnsureSameRequest fails if the key was used for a different request.
func (IdempotencyService) EnsureSameRequest(stored repository.StoredPayment, fingerprint string) error {
	if stored.Fingerprint != fingerprint {
		return apperror.Conflict("Idempotency key was already used with a different request")
	}
	return nil
}
