package controller

import (
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"strings"
	"time"

	"airpay/netbanking/internal/apperror"
	"airpay/netbanking/internal/model"
	"airpay/netbanking/internal/service"
)

// This file is the serializer layer: the exact shapes the API sends and receives.

type createPaymentRequest struct {
	Amount    *model.Amount `json:"amount"`
	Currency  string        `json:"currency"`
	BankCode  string        `json:"bank_code"`
	ReturnURL string        `json:"return_url"`
	Reference string        `json:"reference"`
}

func (r createPaymentRequest) toInput() service.CreatePaymentInput {
	var amount model.Amount
	if r.Amount != nil {
		amount = *r.Amount
	}
	return service.CreatePaymentInput{
		Amount:    amount,
		Currency:  r.Currency,
		BankCode:  r.BankCode,
		ReturnURL: r.ReturnURL,
		Reference: r.Reference,
	}
}

type bankView struct {
	Code string `json:"code"`
	Name string `json:"name"`
}

type paymentView struct {
	TransactionID string   `json:"transaction_id"`
	Status        string   `json:"status"`
	Amount        string   `json:"amount"`
	Currency      string   `json:"currency"`
	Bank          bankView `json:"bank"`
	RedirectURL   string   `json:"redirect_url,omitempty"`
	ReturnURL     string   `json:"return_url"`
	Reference     string   `json:"reference,omitempty"`
	BankReference string   `json:"bank_reference,omitempty"`
	FailureReason string   `json:"failure_reason,omitempty"`
	CreatedAt     string   `json:"created_at"`
	ExpiresAt     string   `json:"expires_at"`
	CompletedAt   string   `json:"completed_at,omitempty"`
}

// toPaymentView maps a payment to its API shape. redirect_url is only present while the
// customer can still pay.
func toPaymentView(p model.Payment, baseURL string) paymentView {
	view := paymentView{
		TransactionID: p.TransactionID,
		Status:        string(p.Status),
		Amount:        p.Amount.String(),
		Currency:      p.Currency,
		Bank:          bankView{Code: p.BankCode, Name: p.BankName},
		ReturnURL:     p.ReturnURL,
		Reference:     p.Reference,
		BankReference: p.BankReference,
		FailureReason: p.FailureReason,
		CreatedAt:     formatTime(p.CreatedAt),
		ExpiresAt:     formatTime(p.ExpiresAt),
	}
	if p.Status == model.StatusPending {
		view.RedirectURL = baseURL + "/bank/" + p.TransactionID
	}
	if p.CompletedAt != nil {
		view.CompletedAt = formatTime(*p.CompletedAt)
	}
	return view
}

type bankListItem struct {
	Code   string `json:"code"`
	Name   string `json:"name"`
	Status string `json:"status"`
}

type bankListView struct {
	Banks []bankListItem `json:"banks"`
}

type healthView struct {
	Status  string   `json:"status"`
	Service string   `json:"service"`
	Banks   []string `json:"banks"`
}

// formatTime writes a UTC timestamp with microseconds, for example
// 2026-10-18T12:13:18.486954Z, the same format the card payment service uses.
func formatTime(t time.Time) string {
	return t.UTC().Format("2006-01-02T15:04:05.000000Z")
}

// decodeJSON reads exactly one JSON object from the body and rejects unknown fields,
// so a misspelt field is an error instead of being silently ignored.
func decodeJSON(r *http.Request, dst any) error {
	decoder := json.NewDecoder(r.Body)
	decoder.DisallowUnknownFields()

	if err := decoder.Decode(dst); err != nil {
		return translateDecodeError(err)
	}
	if _, err := decoder.Token(); !errors.Is(err, io.EOF) {
		var tooLarge *http.MaxBytesError
		if errors.As(err, &tooLarge) {
			return translateDecodeError(err)
		}
		return apperror.BadRequest("Request body must contain a single JSON object")
	}
	return nil
}

func translateDecodeError(err error) error {
	var (
		tooLarge  *http.MaxBytesError
		typeError *json.UnmarshalTypeError
		syntax    *json.SyntaxError
		amount    *model.AmountError
	)
	switch {
	case errors.As(err, &tooLarge):
		return apperror.TooLarge("Request body is too large")
	case errors.Is(err, io.EOF):
		return apperror.BadRequest("Request body is required")
	case errors.As(err, &amount):
		return apperror.Validation(apperror.Field("amount", amount.Reason))
	case errors.As(err, &typeError):
		field := typeError.Field
		if field == "" {
			field = "body"
		}
		return apperror.Validation(apperror.Field(field, "has the wrong type"))
	case strings.HasPrefix(err.Error(), "json: unknown field "):
		name := strings.Trim(strings.TrimPrefix(err.Error(), "json: unknown field "), `"`)
		return apperror.Validation(apperror.Field(name, "unknown field"))
	case errors.As(err, &syntax), errors.Is(err, io.ErrUnexpectedEOF):
		return apperror.BadRequest("Request body is not valid JSON")
	default:
		return apperror.BadRequest("Request body is not valid JSON")
	}
}
