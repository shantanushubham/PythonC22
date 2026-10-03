"""
Thin client for the external payment-gateway service.

Contract (observed from the gateway's docs):

  POST {PAYMENT_GATEWAY_BASE_URL}/api/transactions
    body: {accountNumber, ifsc, accountName, bankName, transactionType, amount}

    200 {"success": true,  "data": {"transactionId": "txn_...", "status": "SUCCESS", ...}}
    402 {"success": false, "data": {"transactionId": "txn_...", "status": "FAILED",
                                     "failureReason": "..."}}
    400 {"success": false, "message": "Validation failed", "errors": [...]}

  200 and 402 both represent a *completed* gateway call with a real
  transactionId — the 402 is a legitimate bank-side decline, not an error on
  our end, so it's treated as a normal (failed) result rather than raised.

  400 means the gateway rejected our request as malformed — that's a real
  error on our side, so it's raised as PaymentGatewayError.
"""

import logging
from decimal import Decimal
from typing import Any

from django.conf import settings
from httpx import AsyncClient

logger = logging.getLogger(__name__)


class PaymentGatewayError(Exception):
    """
    Raised when the gateway call could not be completed at all — network
    failure, unreachable service, malformed request (HTTP 400), or an
    unparsable response. NOT raised for a legitimate bank-side decline
    (HTTP 402) — that's a normal FAILED outcome, not a gateway error.
    """


async def create_bank_transaction(
    *,
    account_no: str,
    ifsc_code: str,
    account_name: str,
    bank_name: str,
    transaction_type: str,
    amount: Decimal,
) -> dict[str, Any]:
    """
    Calls the gateway to create a bank-side transaction and returns its
    `data` object, e.g.:

      {"transactionId": "txn_...", "status": "SUCCESS", ...}
      {"transactionId": "txn_...", "status": "FAILED", "failureReason": "..."}

    Raises PaymentGatewayError if the gateway is unreachable or rejects the
    request outright (HTTP 400).
    """
    url = f"{settings.PAYMENT_GATEWAY_BASE_URL}/api/transactions"
    payload = {
        "accountNumber": account_no,
        "ifsc": ifsc_code,
        "accountName": account_name,
        "bankName": bank_name,
        "transactionType": transaction_type,
        "amount": float(amount),
    }

    logger.info(
        "func=create_bank_transaction message=calling payment gateway "
        "account_no=%s transaction_type=%s amount=%s",
        account_no, transaction_type, amount,
    )

    try:
        # `await` suspends this coroutine while waiting on the gateway, so the
        # event loop can serve other requests in the meantime.
        async with AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=10)
    except httpx.RequestError as exc:  # connect errors, timeouts, etc.
        logger.error(
            "func=create_bank_transaction message=could not reach payment gateway error=%s", exc
        )
        raise PaymentGatewayError(f"Could not reach payment gateway: {exc}") from exc

    try:
        body = response.json()
    except ValueError as exc:
        logger.error(
            "func=create_bank_transaction message=non-JSON response from payment gateway"
        )
        raise PaymentGatewayError(
            "Payment gateway returned a non-JSON response."
        ) from exc

    if response.status_code == 400:
        logger.error(
            "func=create_bank_transaction message=payment gateway rejected request "
            "status_code=%s body=%s",
            response.status_code, body,
        )
        raise PaymentGatewayError(
            body.get("message", "Payment gateway rejected the request.")
        )

    data = body.get("data")
    if data is None:
        logger.error(
            "func=create_bank_transaction message=payment gateway response missing data"
        )
        raise PaymentGatewayError(
            "Payment gateway response did not include transaction data."
        )

    logger.info(
        "func=create_bank_transaction message=payment gateway responded "
        "transaction_id=%s status=%s",
        data.get("transactionId"), data.get("status"),
    )
    return data
