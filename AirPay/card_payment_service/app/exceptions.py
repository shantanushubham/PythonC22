"""Errors the services raise.

Every `DomainError` carries the HTTP status it maps to. The error handler turns any of
them into the standard error response, so adding a new error means adding a subclass.
Nothing else changes.
"""

from app.schemas import FieldError


class DomainError(Exception):
    status_code = 500
    message = "Internal server error"

    def __init__(self, message: str | None = None, errors: list[FieldError] | None = None):
        self.message = message or self.message
        self.errors = errors
        super().__init__(self.message)


class CardValidationError(DomainError):
    status_code = 400
    message = "Validation failed"


class InvalidIdempotencyKeyError(DomainError):
    status_code = 400
    message = "Invalid Idempotency-Key"


class IdempotencyConflictError(DomainError):
    status_code = 409
    message = "Idempotency key was already used with a different request"


class PaymentNotFoundError(DomainError):
    status_code = 404

    def __init__(self, transaction_id: str):
        super().__init__(f"No payment found with id '{transaction_id}'")
