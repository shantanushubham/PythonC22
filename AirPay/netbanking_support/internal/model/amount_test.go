package model_test

import (
	"encoding/json"
	"errors"
	"testing"

	"airpay/netbanking/internal/model"
)

func TestParseAmount(t *testing.T) {
	valid := map[string]model.Amount{
		"1500":       150000,
		"1500.5":     150050,
		"1500.50":    150050,
		"0.01":       1,
		"0.10":       10,
		" 12.34 ":    1234,
		"0001.50":    150,
		"10000000":   model.MaxAmount,
		"9999999.99": 999999999,
	}
	for input, want := range valid {
		got, err := model.ParseAmount(input)
		if err != nil || got != want {
			t.Errorf("ParseAmount(%q) = %d, %v; want %d", input, got, err, want)
		}
	}

	invalid := map[string]string{
		"0":           "amount must be greater than 0",
		"0.00":        "amount must be greater than 0",
		"10000000.01": "amount must not exceed 10000000.00",
		"1.234":       "amount must have at most 2 decimal places",
		"1.2345":      "amount must have at most 2 decimal places",
		"-5":          `amount must be a decimal string such as "1500.50" or a number`,
		"abc":         `amount must be a decimal string such as "1500.50" or a number`,
		"":            `amount must be a decimal string such as "1500.50" or a number`,
		"1e3":         `amount must be a decimal string such as "1500.50" or a number`,
		"1,500":       `amount must be a decimal string such as "1500.50" or a number`,
		".5":          `amount must be a decimal string such as "1500.50" or a number`,
		"NaN":         `amount must be a decimal string such as "1500.50" or a number`,
		"9999999999":  `amount must be a decimal string such as "1500.50" or a number`,
	}
	for input, wantMessage := range invalid {
		_, err := model.ParseAmount(input)
		var amountErr *model.AmountError
		if !errors.As(err, &amountErr) || amountErr.Reason != wantMessage {
			t.Errorf("ParseAmount(%q) error = %v; want %q", input, err, wantMessage)
		}
	}
}

func TestAmountString(t *testing.T) {
	for amount, want := range map[model.Amount]string{
		150050: "1500.50", 1: "0.01", 100: "1.00", 999999999: "9999999.99", model.MaxAmount: "10000000.00",
	} {
		if got := amount.String(); got != want {
			t.Errorf("Amount(%d).String() = %q, want %q", amount, got, want)
		}
	}
}

func TestAmountJSON(t *testing.T) {
	var fromString, fromNumber struct{ A model.Amount }

	if err := json.Unmarshal([]byte(`{"A":"1500.50"}`), &fromString); err != nil || fromString.A != 150050 {
		t.Errorf("string form: %v, %d", err, fromString.A)
	}
	if err := json.Unmarshal([]byte(`{"A":1500.5}`), &fromNumber); err != nil || fromNumber.A != 150050 {
		t.Errorf("number form: %v, %d", err, fromNumber.A)
	}

	out, err := json.Marshal(struct{ A model.Amount }{150050})
	if err != nil || string(out) != `{"A":"1500.50"}` {
		t.Errorf("marshal = %s, %v; want a string", out, err)
	}
}

func TestAmountJSONRejectsNonAmounts(t *testing.T) {
	for _, body := range []string{`{"A":true}`, `{"A":[1]}`, `{"A":{"x":1}}`, `{"A":"abc"}`, `{"A":-1}`, `{"A":0}`} {
		var v struct{ A model.Amount }
		err := json.Unmarshal([]byte(body), &v)
		var amountErr *model.AmountError
		if !errors.As(err, &amountErr) {
			t.Errorf("%s: got %v, want an AmountError", body, err)
		}
	}
}

func TestPaymentStatusFinality(t *testing.T) {
	if model.StatusPending.Final() {
		t.Error("PENDING must not be final")
	}
	for _, s := range []model.PaymentStatus{
		model.StatusSuccess, model.StatusFailed, model.StatusCancelled, model.StatusExpired,
	} {
		if !s.Final() {
			t.Errorf("%s must be final", s)
		}
	}
}
