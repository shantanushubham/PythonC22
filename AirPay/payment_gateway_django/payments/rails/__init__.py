from payments.rails.base import (
    PaymentRail,
    RailConflict,
    RailError,
    RailNotFound,
    RailResult,
    RailUnavailable,
    RailValidation,
)
from payments.rails.card import CardRail
from payments.rails.netbanking import NetbankingRail
from payments.rails.upi import UpiRail

__all__ = [
    "CardRail",
    "NetbankingRail",
    "PaymentRail",
    "RailConflict",
    "RailError",
    "RailNotFound",
    "RailResult",
    "RailUnavailable",
    "RailValidation",
    "UpiRail",
    "get_rail",
]


def get_rail(method: str) -> PaymentRail:
    if method == "CARD":
        return CardRail()
    if method == "UPI":
        return UpiRail()
    if method == "NETBANKING":
        return NetbankingRail()
    raise ValueError(f"unknown payment method {method!r}")
