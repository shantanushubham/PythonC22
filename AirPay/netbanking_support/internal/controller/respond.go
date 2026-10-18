// Package controller turns HTTP requests into service calls and results into responses.
//
// A controller reads the request, calls a service, and shapes the response. It holds no
// business rules. Services return errors, and one error handler here turns them into
// the standard error response, so handlers contain no error formatting.
package controller

import (
	"encoding/json"
	"errors"
	"log/slog"
	"net/http"

	"airpay/netbanking/internal/apperror"
)

// HandlerFunc is a handler that returns its error instead of writing it.
type HandlerFunc func(w http.ResponseWriter, r *http.Request) error

type successBody struct {
	Success bool `json:"success"`
	Data    any  `json:"data"`
}

type errorBody struct {
	Success bool                  `json:"success"`
	Message string                `json:"message"`
	Errors  []apperror.FieldError `json:"errors,omitempty"`
}

// jsonHandler is the error handler: it adapts a HandlerFunc to http.Handler and turns
// any error it returns into the standard error response.
func jsonHandler(logger *slog.Logger, fn HandlerFunc) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if err := fn(w, r); err != nil {
			writeError(logger, w, r, err)
		}
	})
}

func writeError(logger *slog.Logger, w http.ResponseWriter, r *http.Request, err error) {
	var appErr *apperror.Error
	if !errors.As(err, &appErr) {
		logger.Error("unhandled error", "method", r.Method, "path", r.URL.Path, "error", err)
		appErr = &apperror.Error{Status: http.StatusInternalServerError, Message: "Internal server error"}
	}
	writeJSON(w, appErr.Status, errorBody{Success: false, Message: appErr.Message, Errors: appErr.Fields})
}

// writeJSON sends body as JSON. Payment data is never cached.
func writeJSON(w http.ResponseWriter, status int, body any, headers ...[2]string) {
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Cache-Control", "no-store")
	for _, h := range headers {
		w.Header().Set(h[0], h[1])
	}
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(body)
}

func writeSuccess(w http.ResponseWriter, status int, data any, headers ...[2]string) {
	writeJSON(w, status, successBody{Success: true, Data: data}, headers...)
}
