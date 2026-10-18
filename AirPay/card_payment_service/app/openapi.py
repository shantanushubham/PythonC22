"""OpenAPI document for the card payment service.

FastAPI builds most of the spec from the routes and models. This module fixes the
parts it gets wrong for this service: validation errors are returned as 400 (not
FastAPI's default 422), and the info block and tags need real descriptions.
"""

from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

DESCRIPTION = """\
Mock card network for the AirPay payment gateway.

Send card details and the service identifies the network (Visa, Mastercard, Diners,
American Express, or RuPay) and returns an authorization. Nothing is sent to a real
network. Payments are saved to a local SQLite file, so they survive restarts. Only the
last four digits of the card are stored. **Never send real card numbers.**

### Outcomes
* `200` - approved (`data.status` is `SUCCESS`).
* `402` - declined by the issuer (`data.status` is `FAILED`, see `data.failure_reason`).
  A decline is a completed call with a real `transaction_id`, not an error.
* `400` - the request was rejected before reaching a network. No transaction is created.

### Mock issuer decision
The digit before the Luhn check digit of the card number chooses the result:
`0`-`6` approve, `7` insufficient funds, `8` declined by issuer, `9` network timeout.
A CVV of `000` (`0000` for American Express) is declined with `Incorrect CVV`.
"""

TAGS = [
    {"name": "payments", "description": "Authorize debit and credit card payments."},
    {"name": "health", "description": "Service liveness."},
]


def build_openapi(app: FastAPI) -> dict[str, Any]:
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        summary=app.summary,
        description=DESCRIPTION,
        routes=app.routes,
        tags=TAGS,
        servers=[{"url": "http://localhost:8001", "description": "Local development"}],
    )
    _remove_default_validation_errors(schema)
    app.openapi_schema = schema
    return schema


def _remove_default_validation_errors(schema: dict[str, Any]) -> None:
    """Drop FastAPI's 422 responses and their schemas.

    This service answers invalid requests with 400 and its own error envelope.
    """
    for operations in schema.get("paths", {}).values():
        for operation in operations.values():
            operation.get("responses", {}).pop("422", None)

    components = schema.get("components", {}).get("schemas", {})
    components.pop("HTTPValidationError", None)
    components.pop("ValidationError", None)
