"""Types shared by every payment rail (card, UPI, netbanking)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class RailResult:
    rail_transaction_id: str
    status: str
    amount: str | None = None
    rail_reference: str = ""
    failure_reason: str = ""
    failure_code: str = ""
    instrument: dict = field(default_factory=dict)
    redirect_url: str = ""
    replayed: bool = False


class RailError(Exception):
    pass


class RailValidation(RailError):
    def __init__(self, errors: list[dict]):
        self.errors = errors
        super().__init__("Validation failed")


class RailConflict(RailError):
    pass


class RailNotFound(RailError):
    def __init__(self, rail_transaction_id: str):
        self.rail_transaction_id = rail_transaction_id
        super().__init__(f"Unknown rail transaction {rail_transaction_id}")


class RailUnavailable(RailError):
    def __init__(self, message: str = "The payment rail is unavailable."):
        self.message = message
        super().__init__(message)


class PaymentRail(Protocol):
    def create(self, payload: dict, idempotency_key: str = "") -> RailResult: ...

    def fetch(self, rail_transaction_id: str) -> RailResult: ...
