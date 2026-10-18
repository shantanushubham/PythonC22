/**
 * Errors the services throw.
 *
 * Every DomainError carries the HTTP status it maps to. The error handler turns any of
 * them into the standard error response, so adding an error means adding a subclass.
 */

export interface FieldError {
  field: string;
  message: string;
}

export class DomainError extends Error {
  readonly statusCode: number;
  readonly errors: FieldError[] | undefined;

  constructor(message: string, statusCode: number, errors?: FieldError[]) {
    super(message);
    this.name = new.target.name;
    this.statusCode = statusCode;
    this.errors = errors;
  }
}

export class RequestValidationError extends DomainError {
  constructor(errors: FieldError[], message = "Validation failed") {
    super(message, 400, errors);
  }
}

export class InvalidIdempotencyKeyError extends DomainError {
  constructor() {
    super(
      "Idempotency-Key must be 1-255 characters and use only letters, digits, and . _ : -",
      400,
    );
  }
}

export class IdempotencyConflictError extends DomainError {
  constructor() {
    super("Idempotency key was already used with a different request", 409);
  }
}

export class PaymentNotFoundError extends DomainError {
  constructor(transactionId: string) {
    super(`No payment found with id '${transactionId}'`, 404);
  }
}
