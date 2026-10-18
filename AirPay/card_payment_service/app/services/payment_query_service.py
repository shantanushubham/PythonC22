"""Looks up payments that were already authorized."""

from app.exceptions import PaymentNotFoundError
from app.models import PaymentRecord
from app.repositories.payment_repository import PaymentReader


class PaymentQueryService:
    """Depends on `PaymentReader` only, so it cannot create or change payments."""

    def __init__(self, reader: PaymentReader) -> None:
        self._reader = reader

    def get(self, transaction_id: str) -> PaymentRecord:
        stored = self._reader.get(transaction_id)
        if stored is None:
            raise PaymentNotFoundError(transaction_id)
        return stored.record
