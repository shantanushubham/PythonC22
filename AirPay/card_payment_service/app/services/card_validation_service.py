"""Checks that a card can be sent to a network. It does not authorize anything."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from app.exceptions import CardValidationError
from app.networks import CardNetwork, NetworkRegistry
from app.schemas import CreatePaymentRequest, FieldError
from app.utils.luhn import luhn_valid


@dataclass(frozen=True)
class ValidCard:
    network: CardNetwork
    pan: str


def card_expired(month: int, year: int, today: date) -> bool:
    """A card is valid through the last day of its expiry month."""
    if year < today.year:
        return True
    return year == today.year and month < today.month


class CardValidationService:
    def __init__(self, registry: NetworkRegistry, today: Callable[[], date] = date.today):
        self._registry = registry
        self._today = today

    def validate(self, request: CreatePaymentRequest) -> ValidCard:
        """Return the validated card, or raise CardValidationError listing every problem."""
        card = request.card
        profile = self._registry.identify(card.number)
        errors: list[FieldError] = []

        if not luhn_valid(card.number):
            errors.append(
                FieldError(field="card.number", message="card number failed the Luhn check")
            )

        if profile is None:
            errors.append(
                FieldError(
                    field="card.number",
                    message=(
                        "card number does not match Visa, Mastercard, Diners, "
                        "American Express, or RuPay"
                    ),
                )
            )
        elif len(card.cvv) != profile.cvv_length:
            errors.append(
                FieldError(
                    field="card.cvv",
                    message=f"cvv must be {profile.cvv_length} digits for {profile.network.value}",
                )
            )

        if card_expired(card.expiry_month, card.expiry_year, self._today()):
            errors.append(FieldError(field="card.expiry_year", message="card is expired"))

        if errors or profile is None:
            raise CardValidationError(errors=errors)

        return ValidCard(network=profile.network, pan=card.number)
