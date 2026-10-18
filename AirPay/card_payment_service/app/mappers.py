"""Mappers: build a stored `PaymentRecord` from a request and its decision."""

import secrets
import string
from datetime import datetime, timezone
from uuid import uuid4

from app.models import CardSummary, PaymentRecord
from app.schemas import CreatePaymentRequest
from app.services.card_validation_service import ValidCard
from app.services.issuer_decision_service import Decision

_AUTH_ALPHABET = string.ascii_uppercase + string.digits


class PaymentMapper:
    def to_record(
        self,
        request: CreatePaymentRequest,
        card: ValidCard,
        decision: Decision,
    ) -> PaymentRecord:
        now = datetime.now(timezone.utc)
        approved = decision.status == "SUCCESS"
        return PaymentRecord(
            transaction_id=f"txn_{uuid4()}",
            status=decision.status,
            amount=request.amount,
            currency=request.currency,
            card=CardSummary(
                network=card.network,
                card_type=request.card_type,
                last4=card.pan[-4:],
                holder_name=request.card.holder_name,
                expiry_month=request.card.expiry_month,
                expiry_year=request.card.expiry_year,
            ),
            authorization_code=_authorization_code() if approved else None,
            network_reference=f"{secrets.randbelow(10**12):012d}",
            failure_reason=decision.failure_reason,
            reference=request.reference,
            created_at=now,
            processed_at=now,
        )


def _authorization_code() -> str:
    return "".join(secrets.choice(_AUTH_ALPHABET) for _ in range(6))
