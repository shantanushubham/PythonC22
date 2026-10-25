"""Amounts in whole paise.

A rupee is 100 paise. Integers avoid the rounding errors floats have, so 0.1 + 0.2
never turns into 0.30000000000000004. The API sends and receives a string such as
``"1500.50"``. A number is accepted on the way in.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

# 1,00,00,000.00 rupees. Same ceiling as the card and netbanking services.
MAX_PAISE = 1_000_000_000
MIN_PAYOUT_PAISE = 100  # ₹1
MIN_UPI_PAISE = 100  # ₹1 — the UPI service rejects anything smaller

_TOO_MANY_DECIMALS = re.compile(r"^\d+\.\d{3,}$")
_AMOUNT = re.compile(r"^\d{1,9}(\.\d{1,2})?$")


class AmountError(ValueError):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def parse_amount(value) -> int:
    """Return paise. Accepts ``"1500.50"``, ``1500.5`` or a Decimal."""
    if value is None or value == "":
        raise AmountError("amount is required")
    if isinstance(value, bool):
        raise AmountError("amount must be a decimal string such as \"1500.50\" or a number")
    if isinstance(value, int):
        text = f"{value}.00"
    elif isinstance(value, Decimal):
        text = format(value, "f")
    elif isinstance(value, float):
        text = format(Decimal(str(value)), "f")
    elif isinstance(value, str):
        text = value.strip()
    else:
        raise AmountError("amount must be a decimal string such as \"1500.50\" or a number")

    if _TOO_MANY_DECIMALS.match(text):
        raise AmountError("amount must have at most 2 decimal places")
    if not _AMOUNT.match(text):
        raise AmountError("amount must be a decimal string such as \"1500.50\" or a number")

    whole, _, fraction = text.partition(".")
    fraction = (fraction + "00")[:2]
    paise = int(whole) * 100 + int(fraction)
    if paise <= 0:
        raise AmountError("amount must be greater than 0")
    if paise > MAX_PAISE:
        raise AmountError("amount must not exceed 10000000.00")
    return paise


def format_amount(paise: int) -> str:
    sign = "-" if paise < 0 else ""
    paise = abs(int(paise))
    return f"{sign}{paise // 100}.{paise % 100:02d}"


@extend_schema_field(
    serializers.CharField(help_text='Amount in rupees, as a string such as "1500.50".')
)
class AmountField(serializers.Field):
    """JSON string in, paise out. Writes a string so clients do not use a float."""

    default_error_messages = {"invalid": "amount is invalid"}

    def to_internal_value(self, data):
        try:
            return parse_amount(data)
        except AmountError as error:
            raise serializers.ValidationError(error.reason) from error

    def to_representation(self, value):
        return format_amount(value)
