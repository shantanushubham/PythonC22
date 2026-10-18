"""SQLite implementation of the payment repository.

Payments are saved to a file, so they survive restarts and are shared by every uvicorn
worker. The unique index on `idempotency_key` is what makes the "one payment per key"
rule atomic across workers.

Only the masked card summary is stored (last four digits). The full card number and
CVV never reach this module.
"""

import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path

from app.models import PaymentRecord
from app.repositories.payment_repository import (
    DuplicateIdempotencyKeyError,
    DuplicatePaymentError,
    PaymentRepository,
    StoredPayment,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS payments (
    transaction_id  TEXT PRIMARY KEY,
    idempotency_key TEXT UNIQUE,
    fingerprint     TEXT NOT NULL,
    status          TEXT NOT NULL,
    record          TEXT NOT NULL,
    created_at      TEXT NOT NULL
)
"""


class SqlitePaymentRepository(PaymentRepository):
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            # WAL lets readers and a writer work at the same time. It is stored in the file.
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(SCHEMA)

    def save(self, payment: StoredPayment) -> None:
        record = payment.record
        try:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO payments (transaction_id, idempotency_key, fingerprint, "
                    "status, record, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        record.transaction_id,
                        payment.idempotency_key,
                        payment.fingerprint,
                        record.status,
                        record.model_dump_json(),
                        record.created_at.isoformat(),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            if "idempotency_key" in str(exc):
                raise DuplicateIdempotencyKeyError(payment.idempotency_key) from exc
            raise DuplicatePaymentError(record.transaction_id) from exc

    def get(self, transaction_id: str) -> StoredPayment | None:
        return self._fetch("transaction_id = ?", transaction_id)

    def get_by_key(self, idempotency_key: str) -> StoredPayment | None:
        return self._fetch("idempotency_key = ?", idempotency_key)

    def _fetch(self, where: str, value: str) -> StoredPayment | None:
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT record, fingerprint, idempotency_key FROM payments WHERE {where}",
                (value,),
            ).fetchone()
        if row is None:
            return None
        record, fingerprint, idempotency_key = row
        return StoredPayment(
            record=PaymentRecord.model_validate_json(record),
            fingerprint=fingerprint,
            idempotency_key=idempotency_key,
        )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """One short-lived connection per operation.

        Connections are not shared between threads or workers. The `with conn` block
        commits on success and rolls back on error.
        """
        # `timeout` makes a writer wait for the lock instead of failing immediately.
        with closing(sqlite3.connect(self.path, timeout=10)) as conn:
            with conn:
                yield conn
