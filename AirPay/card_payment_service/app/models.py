"""Models: the payment data the services and repositories pass around."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_serializer

from app.networks import CardNetwork

CardType = Literal["credit", "debit"]
PaymentStatus = Literal["SUCCESS", "FAILED"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CardSummary(StrictModel):
    """The masked card. The full number and CVV are never part of a stored payment."""

    network: CardNetwork
    card_type: CardType
    last4: str
    holder_name: str
    expiry_month: int
    expiry_year: int


class PaymentRecord(StrictModel):
    transaction_id: str
    status: PaymentStatus
    amount: Decimal
    currency: Literal["INR"]
    card: CardSummary
    authorization_code: str | None = None
    network_reference: str
    failure_reason: str | None = None
    reference: str | None = None
    created_at: datetime
    processed_at: datetime

    @field_serializer("amount")
    def serialize_amount(self, value: Decimal) -> str:
        return f"{value:.2f}"
