"""HTTP contract tests for the mock card payment service.

These go through the controllers, so they check status codes, headers, and bodies.
Business rules are covered in test_services.py.
"""

from fastapi.testclient import TestClient

from app.main import app
from app.networks import CardNetwork, default_registry
from app.utils.luhn import luhn_check_digit

client = TestClient(app)

VISA_SUCCESS = "4111111111111111"
MASTERCARD_SUCCESS = "5555555555554444"
MASTERCARD_2_SERIES = "2223003122003222"
AMEX_SUCCESS = "378282246310005"
DINERS_SUCCESS = "30569309025904"


def card_with_selector(prefix: str, selector: str, length: int) -> str:
    """Build a Luhn-valid PAN of `length` whose digit before the check digit is `selector`."""
    body_length = length - 2
    if len(prefix) > body_length:
        raise ValueError("prefix is longer than the card body")
    payload = prefix + ("0" * (body_length - len(prefix))) + selector
    return payload + luhn_check_digit(payload)


def _cvv_for(number: str) -> str:
    digits = number.replace(" ", "").replace("-", "")
    profile = default_registry().identify(digits)
    if profile is not None and profile.network is CardNetwork.AMERICAN_EXPRESS:
        return "1234"
    return "123"


def payment_body(number: str, **overrides: object) -> dict:
    body = {
        "amount": "1500.50",
        "currency": "INR",
        "card_type": "credit",
        "card": {
            "number": number,
            "expiry_month": 12,
            "expiry_year": 2030,
            "cvv": _cvv_for(number),
            "holder_name": "Jane Doe",
        },
        "reference": "order_1001",
    }
    body.update(overrides)
    return body


def test_health_lists_supported_networks():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "card-payment-service",
        "networks": ["visa", "mastercard", "diners", "american_express", "rupay"],
    }


def test_each_network_can_be_approved():
    rupay = card_with_selector("607484", "1", 16)
    cards = {
        VISA_SUCCESS: "visa",
        MASTERCARD_SUCCESS: "mastercard",
        MASTERCARD_2_SERIES: "mastercard",
        AMEX_SUCCESS: "american_express",
        DINERS_SUCCESS: "diners",
        rupay: "rupay",
    }

    for number, network in cards.items():
        response = client.post("/api/v1/payments", json=payment_body(number))

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["success"] is True
        assert body["data"]["status"] == "SUCCESS"
        assert body["data"]["card"]["network"] == network
        assert body["data"]["card"]["last4"] == number[-4:]
        assert len(body["data"]["authorization_code"]) == 6
        assert len(body["data"]["network_reference"]) == 12
        assert "failure_reason" not in body["data"]
        assert number not in response.text
        assert "cvv" not in body["data"]["card"]


def test_debit_and_credit_are_both_accepted():
    for card_type in ("debit", "credit"):
        response = client.post(
            "/api/v1/payments",
            json=payment_body(VISA_SUCCESS, card_type=card_type),
        )

        assert response.status_code == 200
        assert response.json()["data"]["card"]["card_type"] == card_type


def test_issuer_declines_are_deterministic():
    expected = {
        "7": "Insufficient funds",
        "8": "Transaction declined by issuer",
        "9": "Card network timeout",
    }

    for digit, reason in expected.items():
        number = card_with_selector("411111", digit, 16)
        response = client.post("/api/v1/payments", json=payment_body(number))

        assert response.status_code == 402, response.text
        body = response.json()
        assert body["success"] is False
        assert body["data"]["status"] == "FAILED"
        assert body["data"]["failure_reason"] == reason
        assert "authorization_code" not in body["data"]
        assert body["data"]["transaction_id"].startswith("txn_")


def test_all_zero_cvv_is_declined():
    response = client.post(
        "/api/v1/payments",
        json=payment_body(VISA_SUCCESS, card={
            "number": VISA_SUCCESS,
            "expiry_month": 12,
            "expiry_year": 2030,
            "cvv": "000",
            "holder_name": "Jane Doe",
        }),
    )

    assert response.status_code == 402
    assert response.json()["data"]["failure_reason"] == "Incorrect CVV"


def test_failed_payment_can_be_fetched():
    number = card_with_selector("411111", "7", 16)
    created = client.post("/api/v1/payments", json=payment_body(number))
    transaction_id = created.json()["data"]["transaction_id"]

    fetched = client.get(f"/api/v1/payments/{transaction_id}")

    assert fetched.status_code == 200
    assert fetched.json()["success"] is True
    assert fetched.json()["data"]["status"] == "FAILED"
    assert fetched.json()["data"]["transaction_id"] == transaction_id


def test_unknown_transaction_is_not_found():
    response = client.get("/api/v1/payments/txn_missing")

    assert response.status_code == 404
    assert response.json()["success"] is False


def test_unknown_route_uses_the_error_envelope():
    response = client.get("/nope")

    assert response.status_code == 404
    assert response.json() == {
        "success": False,
        "message": "Route GET /nope not found",
    }


def test_idempotency_key_replays_the_original_payment():
    first = client.post(
        "/api/v1/payments",
        json=payment_body(VISA_SUCCESS),
        headers={"Idempotency-Key": "order-replay-1"},
    )
    second = client.post(
        "/api/v1/payments",
        json=payment_body(VISA_SUCCESS),
        headers={"Idempotency-Key": "order-replay-1"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.headers["idempotent-replayed"] == "true"
    assert second.json()["data"]["transaction_id"] == first.json()["data"]["transaction_id"]


def test_idempotency_key_rejects_a_different_body():
    client.post(
        "/api/v1/payments",
        json=payment_body(VISA_SUCCESS, reference="order_a"),
        headers={"Idempotency-Key": "order-conflict-1"},
    )
    response = client.post(
        "/api/v1/payments",
        json=payment_body(VISA_SUCCESS, reference="order_b"),
        headers={"Idempotency-Key": "order-conflict-1"},
    )

    assert response.status_code == 409
    assert response.json()["success"] is False


def test_validation_errors_use_the_error_envelope():
    response = client.post("/api/v1/payments", json={"amount": "0", "card_type": "credit"})

    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["message"] == "Validation failed"
    assert body["errors"]


def test_luhn_failure_and_unknown_network_are_rejected():
    bad_luhn = client.post("/api/v1/payments", json=payment_body("4111111111111112"))
    unknown = client.post("/api/v1/payments", json=payment_body(card_with_selector("999999", "1", 16)))

    assert bad_luhn.status_code == 400
    assert any(error["field"] == "card.number" for error in bad_luhn.json()["errors"])
    assert unknown.status_code == 400
    assert "RuPay" in unknown.json()["errors"][0]["message"]


def test_expired_card_and_wrong_cvv_length_are_rejected():
    expired = payment_body(VISA_SUCCESS)
    expired["card"]["expiry_month"] = 1
    expired["card"]["expiry_year"] = 2020
    expired_response = client.post("/api/v1/payments", json=expired)

    amex = payment_body(AMEX_SUCCESS)
    amex["card"]["cvv"] = "123"
    amex_response = client.post("/api/v1/payments", json=amex)

    assert expired_response.status_code == 400
    assert amex_response.status_code == 400
    assert any(error["field"] == "card.cvv" for error in amex_response.json()["errors"])


def test_spaced_card_number_is_accepted_and_amount_keeps_two_decimals():
    body = payment_body("4111 1111 1111 1111", amount=1500.5)
    response = client.post("/api/v1/payments", json=body)

    assert response.status_code == 200
    assert response.json()["data"]["amount"] == "1500.50"
    assert response.json()["data"]["card"]["last4"] == "1111"
