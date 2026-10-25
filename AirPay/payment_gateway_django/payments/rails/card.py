from django.conf import settings

from payments.rails.base import RailResult
from payments.rails.http import raise_for_status, replayed, request_json, unwrap


class CardRail:
    def __init__(self, base_url: str | None = None, timeout: float | None = None):
        self.base_url = (base_url or settings.CARD_PAYMENT_URL).rstrip("/")
        self.timeout = timeout if timeout is not None else settings.RAIL_TIMEOUT_SECONDS

    def create(self, payload: dict, idempotency_key: str = "") -> RailResult:
        status, body, headers = request_json(
            "POST",
            f"{self.base_url}/api/v1/payments",
            json_body=payload,
            headers={"Idempotency-Key": idempotency_key} if idempotency_key else None,
            timeout=self.timeout,
            service="card payment service",
        )
        raise_for_status(status, body)
        return _from_card(unwrap(body), replayed(headers))

    def fetch(self, rail_transaction_id: str) -> RailResult:
        status, body, headers = request_json(
            "GET",
            f"{self.base_url}/api/v1/payments/{rail_transaction_id}",
            timeout=self.timeout,
            service="card payment service",
        )
        raise_for_status(status, body, rail_transaction_id=rail_transaction_id)
        return _from_card(unwrap(body), replayed(headers))


def _from_card(data: dict, was_replayed: bool) -> RailResult:
    card = data.get("card") or {}
    return RailResult(
        rail_transaction_id=data["transaction_id"],
        status=data["status"],
        amount=data.get("amount"),
        rail_reference=data.get("authorization_code") or data.get("network_reference") or "",
        failure_reason=data.get("failure_reason") or "",
        instrument={
            "last_four": card.get("last4") or "",
            "network": card.get("network") or "",
            "card_type": card.get("card_type") or "",
            "holder_name": card.get("holder_name") or "",
        },
        replayed=was_replayed,
    )
