from django.conf import settings

from payments.rails.base import RailResult
from payments.rails.http import raise_for_status, replayed, request_json, unwrap


class UpiRail:
    def __init__(self, base_url: str | None = None, timeout: float | None = None):
        self.base_url = (base_url or settings.UPI_PAYMENT_URL).rstrip("/")
        self.timeout = timeout if timeout is not None else settings.RAIL_TIMEOUT_SECONDS

    def create(self, payload: dict, idempotency_key: str = "") -> RailResult:
        status, body, headers = request_json(
            "POST",
            f"{self.base_url}/api/v1/payments",
            json_body=payload,
            headers={"Idempotency-Key": idempotency_key} if idempotency_key else None,
            timeout=self.timeout,
            service="UPI payment service",
        )
        raise_for_status(status, body)
        return _from_upi(unwrap(body), replayed(headers))

    def fetch(self, rail_transaction_id: str) -> RailResult:
        status, body, headers = request_json(
            "GET",
            f"{self.base_url}/api/v1/payments/{rail_transaction_id}",
            timeout=self.timeout,
            service="UPI payment service",
        )
        raise_for_status(status, body, rail_transaction_id=rail_transaction_id)
        return _from_upi(unwrap(body), replayed(headers))


def _from_upi(data: dict, was_replayed: bool) -> RailResult:
    payer = data.get("payer") or {}
    return RailResult(
        rail_transaction_id=data["transaction_id"],
        status=data["status"],
        amount=data.get("amount"),
        rail_reference=data.get("rrn") or "",
        failure_reason=data.get("failure_reason") or "",
        failure_code=data.get("failure_code") or "",
        instrument={
            "payer_vpa": payer.get("vpa") or "",
            "payer_name": payer.get("name") or "",
        },
        replayed=was_replayed,
    )
