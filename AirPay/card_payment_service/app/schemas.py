"""Serializers: request and response shapes of the HTTP API."""

from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import ConfigDict, Field, field_serializer, field_validator

from app.models import CardType, PaymentRecord, StrictModel
from app.networks import CardNetwork

MAX_AMOUNT = Decimal("10000000.00")


class APIModel(StrictModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CardDetails(APIModel):
    number: str = Field(
        pattern=r"^\d{13,19}$",
        description="Primary account number. Spaces and dashes are stripped.",
        examples=["4111111111111111"],
    )
    expiry_month: int = Field(ge=1, le=12, examples=[12])
    expiry_year: int = Field(ge=2000, le=2100, description="Four-digit year.", examples=[2030])
    cvv: str = Field(
        pattern=r"^\d{3,4}$",
        description="3 digits, or 4 digits for American Express.",
        examples=["123"],
    )
    holder_name: str = Field(
        pattern=r"^[A-Za-z][A-Za-z .'\-]{1,99}$",
        examples=["Jane Doe"],
    )

    @field_validator("number", mode="before")
    @classmethod
    def strip_card_number(cls, value: object) -> object:
        if isinstance(value, str):
            return value.replace(" ", "").replace("-", "")
        return value


class CreatePaymentRequest(APIModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        json_schema_extra={
            "examples": [
                {
                    "amount": "1500.50",
                    "currency": "INR",
                    "card_type": "credit",
                    "card": {
                        "number": "4111111111111111",
                        "expiry_month": 12,
                        "expiry_year": 2030,
                        "cvv": "123",
                        "holder_name": "Jane Doe",
                    },
                    "reference": "order_1001",
                }
            ]
        },
    )

    amount: Decimal = Field(description='Amount in major units, for example "1500.50".')
    currency: Literal["INR"] = "INR"
    card_type: CardType
    card: CardDetails
    reference: str | None = Field(
        default=None,
        max_length=64,
        pattern=r"^[A-Za-z0-9_-]+$",
        description="Your own id for this payment, such as an order id.",
    )

    @field_validator("amount", mode="before")
    @classmethod
    def parse_amount(cls, value: object) -> Decimal:
        return _parse_amount(value)

    @field_serializer("amount")
    def serialize_amount(self, value: Decimal) -> str:
        return f"{value:.2f}"


class PaymentResponse(APIModel):
    success: bool
    data: PaymentRecord


class FieldError(APIModel):
    field: str
    message: str


class ErrorResponse(APIModel):
    success: Literal[False] = False
    message: str
    errors: list[FieldError] | None = None


class HealthResponse(APIModel):
    status: Literal["ok"] = "ok"
    service: Literal["card-payment-service"] = "card-payment-service"
    networks: list[CardNetwork]


def _parse_amount(value: object) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        raise ValueError('amount must be a decimal string such as "1500.50" or a number')

    try:
        amount = value if isinstance(value, Decimal) else Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValueError('amount must be a decimal string such as "1500.50" or a number') from exc

    if not amount.is_finite():
        raise ValueError('amount must be a decimal string such as "1500.50" or a number')

    exponent = amount.as_tuple().exponent
    if not isinstance(exponent, int) or exponent < -2:
        raise ValueError("amount must have at most 2 decimal places")
    if amount <= 0:
        raise ValueError("amount must be greater than 0")
    if amount > MAX_AMOUNT:
        raise ValueError("amount must not exceed 10000000.00")
    return amount.quantize(Decimal("0.01"))
