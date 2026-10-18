package controller

import (
	"testing"

	"airpay/netbanking/internal/model"
)

func TestFormatRupeesUsesIndianGrouping(t *testing.T) {
	cases := map[model.Amount]string{
		1:               "0.01",
		99900:           "999.00",
		100000:          "1,000.00",
		150050:          "1,500.50",
		9999999:         "99,999.99",
		10000000:        "1,00,000.00",
		15000000050:     "15,00,00,000.50",
		model.MaxAmount: "1,00,00,000.00", // 1,000,000,000 paise is 1 crore rupees
		123456789:       "12,34,567.89",
	}
	for amount, want := range cases {
		if got := formatRupees(amount); got != want {
			t.Errorf("formatRupees(%d) = %s, want %s", amount, got, want)
		}
	}
}
