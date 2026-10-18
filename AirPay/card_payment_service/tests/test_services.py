"""Service tests with no HTTP and no database.

Each service is built with plain collaborators, which is possible because they depend
on abstractions (Dependency Inversion).
"""

from datetime import date
from decimal import Decimal

import pytest

from app.container import build_payment_service
from app.exceptions import (
    CardValidationError,
    IdempotencyConflictError,
    InvalidIdempotencyKeyError,
    PaymentNotFoundError,
)
from app.networks import (
    DEFAULT_PROFILES,
    CardNetwork,
    NetworkProfile,
    NetworkRegistry,
    PrefixRange,
    default_registry,
)
from app.repositories.payment_repository import PaymentReader, StoredPayment
from app.services.card_validation_service import CardValidationService, card_expired
from app.services.idempotency_service import IdempotencyService
from app.services.issuer_decision_service import (
    AuthorizationAttempt,
    CardNumberScenarioRule,
    DeclineRule,
    IncorrectCvvRule,
    IssuerDecisionService,
    default_decline_rules,
)
from app.services.payment_query_service import PaymentQueryService
from app.utils.luhn import luhn_check_digit, luhn_valid
from tests.fakes import InMemoryPaymentRepository, make_payment, make_request


def pan_with(prefix: str, selector: str, length: int) -> str:
    body = prefix + "0" * (length - 2 - len(prefix)) + selector
    return body + luhn_check_digit(body)


def attempt(pan: str = "4111111111111111", cvv: str = "123", amount: str = "10.00"):
    return AuthorizationAttempt(pan=pan, cvv=cvv, amount=Decimal(amount))


# --- PaymentService: works with any repository ---------------------------------------


def test_payment_service_runs_on_an_in_memory_repository():
    repository = InMemoryPaymentRepository()
    service = build_payment_service(repository)

    outcome = service.create(make_request(), "key-1")

    assert outcome.record.status == "SUCCESS"
    assert outcome.replayed is False
    assert repository.get(outcome.record.transaction_id) is not None


def test_payment_service_replays_and_detects_conflicts():
    service = build_payment_service(InMemoryPaymentRepository())
    first = service.create(make_request(reference="a"), "key-1")

    replay = service.create(make_request(reference="a"), "key-1")

    assert replay.replayed is True
    assert replay.record.transaction_id == first.record.transaction_id
    with pytest.raises(IdempotencyConflictError):
        service.create(make_request(reference="b"), "key-1")


def test_payments_without_a_key_are_never_replayed():
    service = build_payment_service(InMemoryPaymentRepository())

    first = service.create(make_request(), None)
    second = service.create(make_request(), None)

    assert first.record.transaction_id != second.record.transaction_id
    assert second.replayed is False


def test_invalid_card_is_rejected_and_nothing_is_stored():
    repository = InMemoryPaymentRepository()
    service = build_payment_service(repository)
    bad_card = {
        "number": "4111111111111112",
        "expiry_month": 12,
        "expiry_year": 2030,
        "cvv": "123",
        "holder_name": "Jane Doe",
    }

    with pytest.raises(CardValidationError):
        service.create(make_request(card=bad_card), "key-bad")

    assert repository.get_by_key("key-bad") is None


# --- Open/Closed: extend by adding, not by editing ------------------------------------


def test_new_decline_scenario_is_added_as_a_rule():
    class DeclineLargeAmounts(DeclineRule):
        def check(self, attempt: AuthorizationAttempt) -> str | None:
            return "Amount over limit" if attempt.amount > Decimal("5000") else None

    service = build_payment_service(
        InMemoryPaymentRepository(),
        decline_rules=[*default_decline_rules(), DeclineLargeAmounts()],
    )

    small = service.create(make_request(amount="100.00"), None)
    large = service.create(make_request(amount="9000.00"), None)

    assert small.record.status == "SUCCESS"
    assert large.record.status == "FAILED"
    assert large.record.failure_reason == "Amount over limit"


def test_decline_rules_are_checked_in_order():
    service = IssuerDecisionService([IncorrectCvvRule(), CardNumberScenarioRule()])

    decision = service.decide(attempt(pan=pan_with("411111", "7", 16), cvv="000"))

    assert decision.failure_reason == "Incorrect CVV"


def test_scenario_rule_uses_the_digit_before_the_check_digit():
    rule = CardNumberScenarioRule()

    assert rule.check(attempt(pan=pan_with("411111", "7", 16))) == "Insufficient funds"
    assert rule.check(attempt(pan=pan_with("411111", "8", 16))) == "Transaction declined by issuer"
    assert rule.check(attempt(pan=pan_with("411111", "9", 16))) == "Card network timeout"
    assert rule.check(attempt(pan=pan_with("411111", "3", 16))) is None


def test_issuer_with_no_rules_approves_everything():
    assert IssuerDecisionService([]).decide(attempt()).status == "SUCCESS"


def test_a_network_is_added_by_registering_a_profile():
    pan = pan_with("999999", "1", 16)
    default = default_registry()
    extended = NetworkRegistry(
        [
            *DEFAULT_PROFILES,
            NetworkProfile(CardNetwork.RUPAY, (16,), (PrefixRange(1, 9, 9),)),
        ]
    )

    assert default.identify(pan) is None
    assert extended.identify(pan).network is CardNetwork.RUPAY


# --- CardValidationService -------------------------------------------------------------


def test_card_networks_are_identified_from_the_number():
    registry = default_registry()
    expected = {
        "4111111111111111": CardNetwork.VISA,
        "5555555555554444": CardNetwork.MASTERCARD,
        "2223003122003222": CardNetwork.MASTERCARD,
        "378282246310005": CardNetwork.AMERICAN_EXPRESS,
        "30569309025904": CardNetwork.DINERS,
        pan_with("6521", "1", 16): CardNetwork.RUPAY,
    }

    for pan, network in expected.items():
        assert registry.identify(pan).network is network, pan
    assert registry.identify("1234567890123456") is None


def test_amex_needs_a_four_digit_cvv():
    service = CardValidationService(default_registry(), today=lambda: date(2026, 10, 18))
    amex = {
        "number": "378282246310005",
        "expiry_month": 12,
        "expiry_year": 2030,
        "cvv": "123",
        "holder_name": "Jane Doe",
    }

    with pytest.raises(CardValidationError) as raised:
        service.validate(make_request(card=amex))

    assert [e.field for e in raised.value.errors] == ["card.cvv"]


def test_validation_reports_every_problem_at_once():
    service = CardValidationService(default_registry(), today=lambda: date(2026, 10, 18))
    card = {
        "number": "4111111111111112",
        "expiry_month": 1,
        "expiry_year": 2020,
        "cvv": "123",
        "holder_name": "Jane Doe",
    }

    with pytest.raises(CardValidationError) as raised:
        service.validate(make_request(card=card))

    assert {e.field for e in raised.value.errors} == {"card.number", "card.expiry_year"}


def test_expiry_runs_through_the_end_of_the_month():
    assert card_expired(9, 2026, date(2026, 10, 18)) is True
    assert card_expired(10, 2026, date(2026, 10, 31)) is False
    assert card_expired(12, 2025, date(2026, 1, 1)) is True


def test_luhn():
    assert luhn_valid("4111111111111111")
    assert not luhn_valid("4111111111111112")
    assert luhn_check_digit("411111111111111") == "1"


# --- IdempotencyService ------------------------------------------------------------------


@pytest.mark.parametrize("bad", ["", "   ", "has space", "semi;colon", "x" * 256])
def test_bad_idempotency_keys_are_rejected(bad):
    with pytest.raises(InvalidIdempotencyKeyError):
        IdempotencyService().clean_key(bad)


def test_idempotency_key_is_trimmed_and_optional():
    service = IdempotencyService()

    assert service.clean_key("  order-1 ") == "order-1"
    assert service.clean_key(None) is None


def test_fingerprint_ignores_amount_formatting_but_not_content():
    service = IdempotencyService()

    assert service.fingerprint(make_request(amount="10")) == service.fingerprint(
        make_request(amount="10.00")
    )
    assert service.fingerprint(make_request(amount="10")) != service.fingerprint(
        make_request(amount="11")
    )


# --- PaymentQueryService: Interface Segregation ------------------------------------------


def test_query_service_needs_only_a_reader():
    class ReadOnly(PaymentReader):
        def get(self, transaction_id: str) -> StoredPayment | None:
            return make_payment("txn_ro") if transaction_id == "txn_ro" else None

        def get_by_key(self, idempotency_key: str) -> StoredPayment | None:
            return None

    service = PaymentQueryService(ReadOnly())

    assert service.get("txn_ro").transaction_id == "txn_ro"
    with pytest.raises(PaymentNotFoundError):
        service.get("txn_unknown")
