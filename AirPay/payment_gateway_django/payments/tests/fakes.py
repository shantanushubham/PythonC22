"""In-memory payment rails for tests. No HTTP, no sibling services."""

from __future__ import annotations

import uuid
from dataclasses import replace

from payments.rails.base import RailNotFound, RailResult, RailUnavailable, RailValidation


class FakeRail:
    def __init__(
        self,
        *,
        status: str = "SUCCESS",
        failure_reason: str = "",
        failure_code: str = "",
        redirect_url: str = "",
        instrument: dict | None = None,
    ):
        self.status = status
        self.failure_reason = failure_reason
        self.failure_code = failure_code
        self.redirect_url = redirect_url
        self.instrument = instrument
        self.store: dict[str, RailResult] = {}
        self.calls: list[tuple] = []
        self.unavailable = False
        self.validation_errors: list[dict] | None = None
        self.fetch_status: str | None = None
        self.fetch_failure_reason = ""
        self.fetch_failure_code = ""

    def create(self, payload: dict, idempotency_key: str = "") -> RailResult:
        self.calls.append(("create", payload, idempotency_key))
        if self.unavailable:
            raise RailUnavailable("The payment rail is unavailable.")
        if self.validation_errors:
            raise RailValidation(self.validation_errors)
        rail_id = f"rail_{uuid.uuid4().hex[:12]}"
        result = RailResult(
            rail_transaction_id=rail_id,
            status=self.status,
            amount=payload.get("amount") or None,
            rail_reference="AUTH99" if self.status == "SUCCESS" else "",
            failure_reason=self.failure_reason,
            failure_code=self.failure_code,
            instrument=self.instrument or _instrument_from(payload),
            redirect_url=self.redirect_url if self.status == "PENDING" else "",
        )
        self.store[rail_id] = result
        return result

    def fetch(self, rail_transaction_id: str) -> RailResult:
        self.calls.append(("fetch", rail_transaction_id))
        if self.unavailable:
            raise RailUnavailable("The payment rail is unavailable.")
        result = self.store.get(rail_transaction_id)
        if result is None:
            raise RailNotFound(rail_transaction_id)
        if self.fetch_status:
            result = replace(
                result,
                status=self.fetch_status,
                failure_reason=self.fetch_failure_reason,
                failure_code=self.fetch_failure_code,
                redirect_url="" if self.fetch_status != "PENDING" else result.redirect_url,
                rail_reference=result.rail_reference or ("AUTH99" if self.fetch_status == "SUCCESS" else ""),
            )
            self.store[rail_transaction_id] = result
        return result

    def succeed_pending(self) -> None:
        self.fetch_status = "SUCCESS"
        self.fetch_failure_reason = ""
        self.fetch_failure_code = ""

    def fail_pending(self, reason: str = "Payer declined", code: str = "PAYER_DECLINED") -> None:
        self.fetch_status = "FAILED"
        self.fetch_failure_reason = reason
        self.fetch_failure_code = code


def _instrument_from(payload: dict) -> dict:
    if "card" in payload:
        card = payload.get("card") or {}
        number = str(card.get("number") or "")
        return {
            "last_four": number[-4:] if number else "",
            "network": "visa",
            "card_type": card.get("card_type") or payload.get("card_type") or "",
            "holder_name": card.get("holder_name") or "",
        }
    if "payer_vpa" in payload:
        return {"payer_vpa": payload.get("payer_vpa") or "", "payer_name": "Jane Doe"}
    return {"bank_code": payload.get("bank_code") or "", "bank_name": "HDFC Bank"}


SUCCESS_CARD = {
    "card_type": "credit",
    "number": "4111111111111111",
    "expiry_month": 12,
    "expiry_year": 2030,
    "cvv": "123",
    "holder_name": "Jane Doe",
}


def card_body(amount: str = "1500.50", **extra) -> dict:
    body = {
        "method": "CARD",
        "amount": amount,
        "reference": extra.pop("reference", "order_1"),
        "card": extra.pop("card", SUCCESS_CARD),
    }
    body.update(extra)
    return body
