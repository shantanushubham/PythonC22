package service

import (
	"fmt"
	"strings"

	"airpay/netbanking/internal/model"
)

// Attempt is one customer trying to pay on the bank's page.
type Attempt struct {
	BankCode   string
	CustomerID string
	Password   string
	Amount     model.Amount
}

// String hides the password so an Attempt can never leak it through a log line.
func (a Attempt) String() string {
	return fmt.Sprintf("Attempt{bank=%s customer=%s password=[redacted] amount=%s}",
		a.BankCode, a.CustomerID, a.Amount)
}

// VerdictKind is what the mock bank decided.
type VerdictKind int

const (
	// VerdictApprove: the customer logged in and the bank approves the payment.
	VerdictApprove VerdictKind = iota
	// VerdictInvalidCredentials: the login failed. The customer may try again.
	VerdictInvalidCredentials
	// VerdictDecline: the bank refuses the payment. This is final.
	VerdictDecline
)

// Verdict is the bank's decision. Reason is set for VerdictDecline.
type Verdict struct {
	Kind   VerdictKind
	Reason string
}

// AuthorizationRule is one scenario the mock bank can act out.
//
// Open/Closed: BankAuthorizationService checks a list of rules in order. To add a
// scenario, write a new rule and add it to the list. Nothing existing changes.
type AuthorizationRule interface {
	// Evaluate returns the verdict and true, or false when this rule has no opinion.
	Evaluate(a Attempt) (Verdict, bool)
}

// WrongPasswordRule rejects the password "wrong", so callers can test a failed login.
type WrongPasswordRule struct{}

func (WrongPasswordRule) Evaluate(a Attempt) (Verdict, bool) {
	if a.Password == "wrong" {
		return Verdict{Kind: VerdictInvalidCredentials}, true
	}
	return Verdict{}, false
}

// CustomerScenarioRule declines the payment for certain customer IDs. The customer ID
// picks the scenario, so a test can choose the outcome by what it types in.
type CustomerScenarioRule struct {
	Scenarios map[string]string // lower-case customer ID -> decline reason
}

func (r CustomerScenarioRule) Evaluate(a Attempt) (Verdict, bool) {
	reason, ok := r.Scenarios[strings.ToLower(a.CustomerID)]
	if !ok {
		return Verdict{}, false
	}
	return Verdict{Kind: VerdictDecline, Reason: reason}, true
}

// DefaultAuthorizationRules are the scenarios documented in the README. Any other
// customer ID with any other password is approved.
func DefaultAuthorizationRules() []AuthorizationRule {
	return []AuthorizationRule{
		WrongPasswordRule{},
		CustomerScenarioRule{Scenarios: map[string]string{
			"insufficient": "Insufficient funds",
			"declined":     "Transaction declined by bank",
			"timeout":      "Bank server timeout",
			"locked":       "Customer account is locked",
			"limit":        "Transaction limit exceeded",
		}},
	}
}

// BankAuthorizationService plays the bank: it decides what happens to an attempt.
type BankAuthorizationService struct {
	rules []AuthorizationRule
}

func NewBankAuthorizationService(rules []AuthorizationRule) *BankAuthorizationService {
	return &BankAuthorizationService{rules: rules}
}

// Authorize returns the first rule's verdict, or approves if no rule objects.
func (s *BankAuthorizationService) Authorize(a Attempt) Verdict {
	for _, rule := range s.rules {
		if verdict, ok := rule.Evaluate(a); ok {
			return verdict
		}
	}
	return Verdict{Kind: VerdictApprove}
}
