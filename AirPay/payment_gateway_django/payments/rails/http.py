"""HTTP helper for the card, UPI and netbanking services."""

from __future__ import annotations

import requests

from payments.rails.base import RailConflict, RailNotFound, RailUnavailable, RailValidation


def request_json(
    method: str,
    url: str,
    *,
    json_body: dict | None = None,
    headers: dict | None = None,
    timeout: float = 10,
    service: str = "payment rail",
) -> tuple[int, dict, dict]:
    """Call a rail and return ``(status, body, headers)``.

    An HTTP error status (400, 404, 500 ...) is returned, not raised: ``raise_for_status``
    below decides what each one means. A rail that cannot be reached, times out, or answers
    with something that is not JSON raises ``RailUnavailable``.
    """
    hdrs = {"Accept": "application/json"}
    if headers:
        hdrs.update({key: value for key, value in headers.items() if value})

    try:
        response = requests.request(method, url, json=json_body, headers=hdrs, timeout=timeout)
    except requests.Timeout as error:
        raise RailUnavailable(f"The {service} timed out.") from error
    except requests.RequestException as error:
        raise RailUnavailable(f"The {service} is unavailable.") from error

    try:
        body = response.json() if response.content else {}
    except ValueError:
        # An error page from a proxy is not worth failing on: the status says enough.
        # A success with an unreadable body is not something we can act on.
        if response.ok:
            raise RailUnavailable(f"The {service} sent a reply that could not be read.")
        body = {}
    return response.status_code, body, dict(response.headers)


def unwrap(body: dict) -> dict:
    if isinstance(body, dict) and isinstance(body.get("data"), dict):
        return body["data"]
    return body if isinstance(body, dict) else {}


def raise_for_status(status: int, body: dict, *, rail_transaction_id: str = "") -> None:
    if status in {200, 201, 402}:
        return
    if status == 400:
        errors = body.get("errors") if isinstance(body, dict) else None
        if not isinstance(errors, list):
            errors = [{"field": "non_field_errors", "message": body.get("message", "Validation failed")}]
        raise RailValidation(errors)
    if status == 409:
        raise RailConflict
    if status == 404:
        raise RailNotFound(rail_transaction_id)
    message = body.get("message") if isinstance(body, dict) else None
    raise RailUnavailable(message or "The payment rail is unavailable.")


def replayed(headers: dict) -> bool:
    value = ""
    for key, item in headers.items():
        if key.lower() == "idempotent-replayed":
            value = item
            break
    return str(value).lower() == "true"
