package controller

import (
	"net/http"

	"airpay/netbanking/internal/apperror"
	"airpay/netbanking/internal/service"
)

// PaymentController serves the JSON payment endpoints.
type PaymentController struct {
	payments *service.PaymentService
	query    *service.PaymentQueryService
	baseURL  string
}

func NewPaymentController(
	payments *service.PaymentService,
	query *service.PaymentQueryService,
	baseURL string,
) *PaymentController {
	return &PaymentController{payments: payments, query: query, baseURL: baseURL}
}

// Create handles POST /api/v1/payments.
//
// A new payment returns 201 with the bank page to send the customer to. A retry with
// the same Idempotency-Key and body returns 200 with the same payment, in its current
// state, and an Idempotent-Replayed header.
func (c *PaymentController) Create(w http.ResponseWriter, r *http.Request) error {
	var request createPaymentRequest
	if err := decodeJSON(r, &request); err != nil {
		return err
	}

	var key *string
	if values := r.Header.Values("Idempotency-Key"); len(values) > 1 {
		return apperror.BadRequest("Idempotency-Key must be sent only once")
	} else if len(values) == 1 {
		key = &values[0]
	}

	result, err := c.payments.Create(r.Context(), request.toInput(), key)
	if err != nil {
		return err
	}

	view := toPaymentView(result.Payment, c.baseURL)
	if result.Replayed {
		writeSuccess(w, http.StatusOK, view, [2]string{"Idempotent-Replayed", "true"})
		return nil
	}
	writeSuccess(w, http.StatusCreated, view,
		[2]string{"Location", "/api/v1/payments/" + result.Payment.TransactionID})
	return nil
}

// Get handles GET /api/v1/payments/{transaction_id}.
//
// This is how the caller confirms the outcome after the customer comes back. The
// query string on the return URL can be edited by the customer, so only this answer
// should be trusted.
func (c *PaymentController) Get(w http.ResponseWriter, r *http.Request) error {
	payment, err := c.query.Get(r.Context(), r.PathValue("transaction_id"))
	if err != nil {
		return err
	}
	writeSuccess(w, http.StatusOK, toPaymentView(payment, c.baseURL))
	return nil
}
