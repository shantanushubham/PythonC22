"""The payment repository contract.

Services depend on these abstractions, never on a database. Any implementation must
follow the contract below, so one can replace another without the services noticing
(Liskov Substitution). `tests/test_payment_repository.py` runs the same checks against
every implementation.

Interface Segregation: reading and writing are separate interfaces. Code that only
looks payments up asks for a `PaymentReader` and cannot write.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.models import PaymentRecord


@dataclass(frozen=True)
class StoredPayment:
    record: PaymentRecord
    fingerprint: str
    idempotency_key: str | None


class DuplicatePaymentError(Exception):
    """A payment with this transaction id is already stored."""


class DuplicateIdempotencyKeyError(DuplicatePaymentError):
    """A payment with this idempotency key is already stored."""


class PaymentReader(ABC):
    @abstractmethod
    def get(self, transaction_id: str) -> StoredPayment | None:
        """The payment with this id, or None. Never raises for an unknown id."""

    @abstractmethod
    def get_by_key(self, idempotency_key: str) -> StoredPayment | None:
        """The payment saved under this idempotency key, or None."""


class PaymentWriter(ABC):
    @abstractmethod
    def save(self, payment: StoredPayment) -> None:
        """Store a new payment.

        Raises DuplicateIdempotencyKeyError if the key is already used, and
        DuplicatePaymentError if the transaction id is. A rejected payment is not stored.
        Payments with no idempotency key never collide with each other.
        This check must be atomic: of several concurrent saves with one key, exactly one wins.
        """


class PaymentRepository(PaymentReader, PaymentWriter, ABC):
    """Everything a service that creates payments needs."""
