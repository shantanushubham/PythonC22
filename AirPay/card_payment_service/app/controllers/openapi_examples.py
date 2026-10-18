"""Example bodies shown in the OpenAPI spec and Swagger UI."""

REPLAY_HEADER = {
    "description": "`true` when this is the stored result of an earlier request with the same Idempotency-Key.",
    "schema": {"type": "string", "enum": ["true"]},
}

_CARD_SUMMARY = {
    "network": "visa",
    "card_type": "credit",
    "last4": "1111",
    "holder_name": "Jane Doe",
    "expiry_month": 12,
    "expiry_year": 2030,
}

APPROVED_EXAMPLE = {
    "success": True,
    "data": {
        "transaction_id": "txn_bd87dbbb-c490-42eb-9ba4-a5dd0954f944",
        "status": "SUCCESS",
        "amount": "1500.50",
        "currency": "INR",
        "card": _CARD_SUMMARY,
        "authorization_code": "FQKM8X",
        "network_reference": "907497627294",
        "reference": "order_1001",
        "created_at": "2026-10-18T12:13:18.486954Z",
        "processed_at": "2026-10-18T12:13:18.486954Z",
    },
}

DECLINED_EXAMPLE = {
    "success": False,
    "data": {
        "transaction_id": "txn_4439f2b9-188e-43fc-9017-25e25e9ce042",
        "status": "FAILED",
        "amount": "500.00",
        "currency": "INR",
        "card": {**_CARD_SUMMARY, "last4": "0070"},
        "network_reference": "015408678528",
        "failure_reason": "Insufficient funds",
        "created_at": "2026-10-18T12:13:18.601851Z",
        "processed_at": "2026-10-18T12:13:18.601851Z",
    },
}

VALIDATION_EXAMPLE = {
    "success": False,
    "message": "Validation failed",
    "errors": [{"field": "card.number", "message": "card number failed the Luhn check"}],
}

CONFLICT_EXAMPLE = {
    "success": False,
    "message": "Idempotency key was already used with a different request",
}

SERVER_ERROR_EXAMPLE = {"success": False, "message": "Internal server error"}

NOT_FOUND_EXAMPLE = {
    "success": False,
    "message": "No payment found with id 'txn_missing'",
}
