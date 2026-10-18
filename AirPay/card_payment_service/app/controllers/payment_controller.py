"""HTTP endpoints for payments.

A controller reads the request, calls a service, and turns the result into a response.
Business rules live in the services. Errors are raised by the services and turned into
responses by `app.error_handlers`, so there is no try/except here.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse

from app.container import get_payment_query_service, get_payment_service
from app.controllers import openapi_examples as examples
from app.responses import json_response
from app.schemas import CreatePaymentRequest, ErrorResponse, PaymentResponse
from app.services.payment_query_service import PaymentQueryService
from app.services.payment_service import PaymentService

router = APIRouter(prefix="/api/v1", tags=["payments"])


@router.post(
    "/payments",
    operation_id="createPayment",
    summary="Authorize a debit or credit card payment",
    description=(
        "Identifies the card network from the card number, validates the card, and "
        "returns the issuer decision. Approved payments return 200 and declines return "
        "402. Both carry a `transaction_id`."
    ),
    responses={
        200: {
            "model": PaymentResponse,
            "description": "The card network approved the payment.",
            "headers": {"Idempotent-Replayed": examples.REPLAY_HEADER},
            "content": {"application/json": {"example": examples.APPROVED_EXAMPLE}},
        },
        402: {
            "model": PaymentResponse,
            "description": "The card network declined the payment.",
            "headers": {"Idempotent-Replayed": examples.REPLAY_HEADER},
            "content": {"application/json": {"example": examples.DECLINED_EXAMPLE}},
        },
        400: {
            "model": ErrorResponse,
            "description": "The request failed validation. No transaction is created.",
            "content": {"application/json": {"example": examples.VALIDATION_EXAMPLE}},
        },
        409: {
            "model": ErrorResponse,
            "description": "The Idempotency-Key was already used with a different body.",
            "content": {"application/json": {"example": examples.CONFLICT_EXAMPLE}},
        },
        500: {
            "model": ErrorResponse,
            "description": "Unexpected server error.",
            "content": {"application/json": {"example": examples.SERVER_ERROR_EXAMPLE}},
        },
    },
)
def create_payment(
    payload: CreatePaymentRequest,
    service: Annotated[PaymentService, Depends(get_payment_service)],
    idempotency_key: Annotated[
        str | None,
        Header(
            description=(
                "Optional. Repeating the same key and body returns the original "
                "authorization instead of creating a second one."
            )
        ),
    ] = None,
) -> JSONResponse:
    outcome = service.create(payload, idempotency_key)

    approved = outcome.record.status == "SUCCESS"
    body = PaymentResponse(success=approved, data=outcome.record)
    headers = {"Idempotent-Replayed": "true"} if outcome.replayed else None
    # An issuer decline is a completed call, reported as 402 rather than as an error.
    return json_response(body, 200 if approved else 402, headers)


@router.get(
    "/payments/{transaction_id}",
    operation_id="getPayment",
    summary="Fetch a previously authorized payment",
    description=(
        "Returns the stored payment, whether it was approved or declined. "
        "`success` is true when the payment was found; read `data.status` for the outcome."
    ),
    response_model=PaymentResponse,
    response_model_exclude_none=True,
    responses={
        404: {
            "model": ErrorResponse,
            "description": "Unknown transaction id.",
            "content": {"application/json": {"example": examples.NOT_FOUND_EXAMPLE}},
        },
    },
)
def get_payment(
    transaction_id: str,
    service: Annotated[PaymentQueryService, Depends(get_payment_query_service)],
) -> PaymentResponse:
    return PaymentResponse(success=True, data=service.get(transaction_id))
