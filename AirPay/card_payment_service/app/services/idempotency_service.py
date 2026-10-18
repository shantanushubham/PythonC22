"""Rules for the Idempotency-Key header."""

import hashlib
import json
import re

from app.exceptions import IdempotencyConflictError, InvalidIdempotencyKeyError
from app.repositories.payment_repository import StoredPayment
from app.schemas import CreatePaymentRequest

_KEY_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,255}$")


class IdempotencyService:
    def clean_key(self, value: str | None) -> str | None:
        """The trimmed key, or None when the header was not sent."""
        if value is None:
            return None
        key = value.strip()
        if not _KEY_PATTERN.fullmatch(key):
            raise InvalidIdempotencyKeyError(
                "Idempotency-Key must be 1-255 characters and use only letters, digits, and . _ : -"
            )
        return key

    def fingerprint(self, request: CreatePaymentRequest) -> str:
        """A hash of the request body, used to tell a retry from a different request."""
        payload = request.model_dump(mode="json")
        payload["amount"] = f"{request.amount:.2f}"
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode()).hexdigest()

    def ensure_same_request(self, stored: StoredPayment, fingerprint: str) -> None:
        """Raise IdempotencyConflictError if the key was used for a different request."""
        if stored.fingerprint != fingerprint:
            raise IdempotencyConflictError()
