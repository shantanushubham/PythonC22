"""AirPay's commission on each successful collection.

The rate depends on how the customer's payer paid:

==========================  ======
Credit card, Visa           1%
Credit card, Mastercard     1%
Credit card, Diners         4%
Credit card, American Exp.  4%
Credit card, RuPay          0.5%
Netbanking                  2%
UPI                         1%
==========================  ======

Rates are whole basis points (1 bp = 0.01%), so every calculation stays in
integers. The commission is rounded half up to the nearest paise and is fixed on
the transaction at the moment its wallet is credited. Changing a rate here never
rewrites past transactions.

Debit cards are not in the commission schedule and are charged nothing. To charge
them, add ``("debit", network)`` entries to ``CARD_RATES_BPS``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

NETBANKING_RATE_BPS = 200
UPI_RATE_BPS = 100

# (card_type, network) -> basis points. ``network`` is what the card service reports.
CARD_RATES_BPS: dict[tuple[str, str], int] = {
    ("credit", "visa"): 100,
    ("credit", "mastercard"): 100,
    ("credit", "diners"): 400,
    ("credit", "american_express"): 400,
    ("credit", "rupay"): 50,
}

_BPS = 10_000


@dataclass(frozen=True)
class Commission:
    rate_bps: int
    amount_paise: int


def rate_bps_for(method: str, instrument: dict | None) -> int:
    """Basis points AirPay charges for this payment method and instrument."""
    instrument = instrument or {}
    if method == "UPI":
        return UPI_RATE_BPS
    if method == "NETBANKING":
        return NETBANKING_RATE_BPS
    if method == "CARD":
        card_type = str(instrument.get("card_type") or "").lower()
        network = str(instrument.get("network") or "").lower()
        rate = CARD_RATES_BPS.get((card_type, network))
        if rate is None:
            if card_type == "credit":
                logger.warning("No commission rate for card network %r (%s); charging nothing", network, card_type)
            return 0
        return rate
    return 0


def commission_on(amount_paise: int, rate_bps: int) -> int:
    """``amount_paise * rate``, rounded half up to a whole paise."""
    return (amount_paise * rate_bps + _BPS // 2) // _BPS


def calculate(method: str, instrument: dict | None, amount_paise: int) -> Commission:
    rate = rate_bps_for(method, instrument)
    return Commission(rate_bps=rate, amount_paise=commission_on(amount_paise, rate))


def format_rate(rate_bps: int) -> str:
    """``100`` -> ``"1.00"``, ``50`` -> ``"0.50"`` (percent)."""
    return f"{rate_bps // 100}.{rate_bps % 100:02d}"
