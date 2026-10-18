"""The mock issuer: decides whether a card payment is approved or declined.

Open/Closed: the decision is a list of `DeclineRule`s checked in order. The first rule
that returns a reason declines the payment. To add a scenario, write a new rule and add
it to the list. `IssuerDecisionService` does not change.
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from app.models import PaymentStatus


@dataclass(frozen=True)
class AuthorizationAttempt:
    pan: str
    cvv: str
    amount: Decimal


@dataclass(frozen=True)
class Decision:
    status: PaymentStatus
    failure_reason: str | None = None


class DeclineRule(ABC):
    @abstractmethod
    def check(self, attempt: AuthorizationAttempt) -> str | None:
        """The decline reason, or None when this rule has no objection."""


class IncorrectCvvRule(DeclineRule):
    """A CVV made only of zeros is treated as wrong."""

    def check(self, attempt: AuthorizationAttempt) -> str | None:
        if attempt.cvv.strip("0") == "":
            return "Incorrect CVV"
        return None


class CardNumberScenarioRule(DeclineRule):
    """The digit before the Luhn check digit picks a decline scenario.

    Digits 0-6 are not listed, so ordinary test cards (Visa 4111..., Mastercard 5555...)
    are approved.
    """

    DEFAULT_SCENARIOS = {
        "7": "Insufficient funds",
        "8": "Transaction declined by issuer",
        "9": "Card network timeout",
    }

    def __init__(self, scenarios: dict[str, str] | None = None) -> None:
        self._scenarios = scenarios if scenarios is not None else self.DEFAULT_SCENARIOS

    def check(self, attempt: AuthorizationAttempt) -> str | None:
        return self._scenarios.get(attempt.pan[-2])


def default_decline_rules() -> list[DeclineRule]:
    return [IncorrectCvvRule(), CardNumberScenarioRule()]


class IssuerDecisionService:
    def __init__(self, rules: Sequence[DeclineRule]) -> None:
        self._rules = tuple(rules)

    def decide(self, attempt: AuthorizationAttempt) -> Decision:
        for rule in self._rules:
            reason = rule.check(attempt)
            if reason is not None:
                return Decision(status="FAILED", failure_reason=reason)
        return Decision(status="SUCCESS")
