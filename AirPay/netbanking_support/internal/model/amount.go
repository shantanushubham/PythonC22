package model

import (
	"bytes"
	"encoding/json"
	"fmt"
	"regexp"
	"strconv"
	"strings"
)

// MaxAmount is the largest payment accepted: 10,000,000.00 rupees.
const MaxAmount Amount = 1_000_000_000

// Amount is a sum of money in paise (1/100 rupee). Integers avoid the rounding
// errors floats have, so 0.1 + 0.2 never turns into 0.30000000000000004.
type Amount int64

var amountPattern = regexp.MustCompile(`^\d{1,9}(\.\d{1,2})?$`)
var tooManyDecimals = regexp.MustCompile(`^\d+\.\d{3,}$`)

const amountHint = `amount must be a decimal string such as "1500.50" or a number`

// AmountError explains why an amount was rejected.
type AmountError struct{ Reason string }

func (e *AmountError) Error() string { return e.Reason }

// ParseAmount reads "1500", "1500.5" or "1500.50".
func ParseAmount(s string) (Amount, error) {
	s = strings.TrimSpace(s)
	if tooManyDecimals.MatchString(s) {
		return 0, &AmountError{"amount must have at most 2 decimal places"}
	}
	if !amountPattern.MatchString(s) {
		return 0, &AmountError{amountHint}
	}

	whole, fraction, _ := strings.Cut(s, ".")
	for len(fraction) < 2 {
		fraction += "0"
	}
	// The pattern guarantees digits only and at most 9 whole digits, so neither call
	// can fail or overflow.
	rupees, _ := strconv.ParseInt(whole, 10, 64)
	paise, _ := strconv.ParseInt(fraction, 10, 64)
	amount := Amount(rupees*100 + paise)

	if amount <= 0 {
		return 0, &AmountError{"amount must be greater than 0"}
	}
	if amount > MaxAmount {
		return 0, &AmountError{"amount must not exceed 10000000.00"}
	}
	return amount, nil
}

// String formats the amount with two decimals, for example "1500.50".
func (a Amount) String() string {
	return fmt.Sprintf("%d.%02d", int64(a)/100, int64(a)%100)
}

// MarshalJSON writes the amount as a string so no client turns it into a float.
func (a Amount) MarshalJSON() ([]byte, error) {
	return json.Marshal(a.String())
}

// UnmarshalJSON accepts "1500.50" or 1500.50.
func (a *Amount) UnmarshalJSON(data []byte) error {
	data = bytes.TrimSpace(data)
	if bytes.Equal(data, []byte("null")) {
		return nil
	}

	text := string(data)
	if len(data) > 0 && data[0] == '"' {
		if err := json.Unmarshal(data, &text); err != nil {
			return &AmountError{amountHint}
		}
	}

	parsed, err := ParseAmount(text)
	if err != nil {
		return err
	}
	*a = parsed
	return nil
}
