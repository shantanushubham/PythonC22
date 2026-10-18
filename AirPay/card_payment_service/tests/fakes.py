"""Test doubles and builders."""

from datetime import datetime, timezone
from decimal import Decimal
from threading import Lock

from app.models import CardSummary, PaymentRecord
from app.repositories.payment_repository import (
    DuplicateIdempotencyKeyError,
    DuplicatePaymentError,
    PaymentRepository,
    StoredPayment,
)
from app.schemas import CreatePaymentRequest


class InMemoryPaymentRepository(PaymentRepository):
    """A second implementation of the repository contract, used to prove substitutability."""

    def __init__(self) -> None:
        self._by_id: dict[str, StoredPayment] = {}
        self._by_key: dict[str, StoredPayment] = {}
        self._lock = Lock()

    def save(self, payment: StoredPayment) -> None:
        with self._lock:
            key = payment.idempotency_key
            if key is not None and key in self._by_key:
                raise DuplicateIdempotencyKeyError(key)
            if payment.record.transaction_id in self._by_id:
                raise DuplicatePaymentError(payment.record.transaction_id)
            self._by_id[payment.record.transaction_id] = payment
            if key is not None:
                self._by_key[key] = payment

    def get(self, transaction_id: str) -> StoredPayment | None:
        with self._lock:
            return self._by_id.get(transaction_id)

    def get_by_key(self, idempotency_key: str) -> StoredPayment | None:
        with self._lock:
            return self._by_key.get(idempotency_key)


def make_record(transaction_id: str, status: str = "SUCCESS") -> PaymentRecord:
    now = datetime(2026, 10, 18, 12, 0, 0, 123456, tzinfo=timezone.utc)
    return PaymentRecord(
        transaction_id=transaction_id,
        status=status,
        amount=Decimal("1500.50"),
        currency="INR",
        card=CardSummary(
            network="visa",
            card_type="credit",
            last4="1111",
            holder_name="Jane Doe",
            expiry_month=12,
            expiry_year=2030,
        ),
        authorization_code="ABC123" if status == "SUCCESS" else None,
        network_reference="123456789012",
        failure_reason=None if status == "SUCCESS" else "Insufficient funds",
        reference="order_1",
        created_at=now,
        processed_at=now,
    )


def make_payment(
    transaction_id: str,
    key: str | None = None,
    status: str = "SUCCESS",
    fingerprint: str = "fp-1",
) -> StoredPayment:
    return StoredPayment(
        record=make_record(transaction_id, status),
        fingerprint=fingerprint,
        idempotency_key=key,
    )


def make_request(**overrides: object) -> CreatePaymentRequest:
    body = {
        "amount": "10.00",
        "card_type": "debit",
        "card": {
            "number": "4111111111111111",
            "expiry_month": 12,
            "expiry_year": 2030,
            "cvv": "123",
            "holder_name": "Jane Doe",
        },
    }
    body.update(overrides)
    return CreatePaymentRequest.model_validate(body)
