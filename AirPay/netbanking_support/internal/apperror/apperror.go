// Package apperror defines the errors services return and how they map to HTTP.
//
// Every *Error carries the HTTP status it maps to. The controller layer turns any of
// them into the standard error response, so adding a new kind of error means adding a
// constructor here and nothing else changes.
package apperror

import "net/http"

// FieldError points at one invalid field in a request.
type FieldError struct {
	Field   string `json:"field"`
	Message string `json:"message"`
}

// Error is a failure with a known HTTP status.
type Error struct {
	Status  int
	Message string
	Fields  []FieldError
}

func (e *Error) Error() string { return e.Message }

// Field builds a FieldError.
func Field(field, message string) FieldError {
	return FieldError{Field: field, Message: message}
}

// Validation is a 400 listing every invalid field.
func Validation(fields ...FieldError) *Error {
	return &Error{Status: http.StatusBadRequest, Message: "Validation failed", Fields: fields}
}

// BadRequest is a 400 for a request that cannot be understood at all.
func BadRequest(message string) *Error {
	return &Error{Status: http.StatusBadRequest, Message: message}
}

// NotFound is a 404.
func NotFound(message string) *Error {
	return &Error{Status: http.StatusNotFound, Message: message}
}

// Conflict is a 409.
func Conflict(message string) *Error {
	return &Error{Status: http.StatusConflict, Message: message}
}

// TooLarge is a 413.
func TooLarge(message string) *Error {
	return &Error{Status: http.StatusRequestEntityTooLarge, Message: message}
}

// Unavailable is a 503, used when a bank cannot take payments right now.
func Unavailable(message string) *Error {
	return &Error{Status: http.StatusServiceUnavailable, Message: message}
}
