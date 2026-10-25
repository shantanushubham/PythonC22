"""Transactions (money in through AirPay) and payouts (bank transfers out)."""

from __future__ import annotations

import secrets
import uuid

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from core.money import MIN_PAYOUT_PAISE, AmountError, format_amount, parse_amount
from customers.models import BankAccount, Customer
from payments import commission
from payments.exceptions import ServiceUnavailable
from payments.idempotency import fingerprint
from payments.models import Payout, Settlement, Transaction, Wallet
from payments.rails import (
    RailConflict,
    RailNotFound,
    RailResult,
    RailUnavailable,
    RailValidation,
    get_rail,
)
from payments.wallet import (
    InsufficientSettled,
    InsufficientUnsettled,
    NothingToSettle,
    credit_collection,
    debit_payout,
    get_or_create_wallet,
    reverse_payout,
    settle as move_to_settled,
)


class IdempotencyConflict(Exception):
    pass


def _request_fingerprint(
    method: str,
    amount_paise: int,
    reference: str,
    *,
    card: dict | None = None,
    payer_vpa: str = "",
    description: str = "",
    bank_code: str = "",
    return_url: str = "",
) -> str:
    if method == Transaction.Method.CARD:
        card = card or {}
        return fingerprint(
            method,
            amount_paise,
            reference,
            card.get("card_type"),
            card.get("number"),
            card.get("expiry_month"),
            card.get("expiry_year"),
            card.get("holder_name"),
        )
    if method == Transaction.Method.UPI:
        return fingerprint(method, amount_paise, reference, payer_vpa, description)
    return fingerprint(method, amount_paise, reference, bank_code, return_url)


def _rail_payload(
    method: str,
    amount_paise: int,
    reference: str,
    *,
    card: dict | None = None,
    payer_vpa: str = "",
    description: str = "",
    bank_code: str = "",
    return_url: str = "",
) -> dict:
    amount = format_amount(amount_paise)
    if method == Transaction.Method.CARD:
        card = card or {}
        body = {
            "amount": amount,
            "currency": "INR",
            "card_type": card["card_type"],
            "card": {
                "number": card["number"],
                "expiry_month": card["expiry_month"],
                "expiry_year": card["expiry_year"],
                "cvv": card["cvv"],
                "holder_name": card["holder_name"],
            },
        }
        if reference:
            body["reference"] = reference
        return body
    if method == Transaction.Method.UPI:
        body = {"amount": amount, "currency": "INR", "payer_vpa": payer_vpa}
        if description:
            body["description"] = description
        if reference:
            body["reference"] = reference
        return body
    body = {"amount": amount, "currency": "INR", "bank_code": bank_code, "return_url": return_url}
    if reference:
        body["reference"] = reference
    return body


def _rail_errors(errors: list[dict]) -> dict:
    mapped: dict[str, list[str]] = {}
    for item in errors:
        field = item.get("field") or "non_field_errors"
        mapped.setdefault(field, []).append(item.get("message") or "invalid")
    return mapped


def _call_rail(method: str, payload: dict, idempotency_key: str) -> RailResult:
    try:
        return get_rail(method).create(payload, idempotency_key)
    except RailValidation as error:
        raise ValidationError(_rail_errors(error.errors)) from error
    except RailConflict as error:
        raise IdempotencyConflict from error
    except RailUnavailable as error:
        raise ServiceUnavailable(error.message) from error


def _credit(txn: Transaction) -> None:
    """Credit the wallet for a successful transaction, net of commission. Call under the row lock."""
    fee = commission.calculate(txn.method, txn.instrument, txn.amount_paise)
    credit_collection(txn.customer, txn.amount_paise, txn.id, commission_paise=fee.amount_paise)
    txn.commission_rate_bps = fee.rate_bps
    txn.commission_paise = fee.amount_paise
    txn.credited_at = timezone.now()


@transaction.atomic
def apply_outcome(txn: Transaction, result: RailResult) -> Transaction:
    """Write the rail's answer. Credit the wallet only the first time it is SUCCESS."""
    locked = Transaction.objects.select_for_update().get(pk=txn.pk)
    if locked.status in Transaction.FINAL_STATUSES:
        if locked.status == Transaction.Status.SUCCESS and locked.credited_at is None:
            _credit(locked)
            locked.save(update_fields=["credited_at", "commission_rate_bps", "commission_paise"])
        return locked

    locked.rail_transaction_id = result.rail_transaction_id or locked.rail_transaction_id
    locked.rail_reference = result.rail_reference or locked.rail_reference
    locked.failure_reason = result.failure_reason
    locked.failure_code = result.failure_code
    if result.instrument:
        locked.instrument = result.instrument
    locked.redirect_url = result.redirect_url

    if result.amount:
        try:
            rail_paise = parse_amount(result.amount)
        except AmountError:
            rail_paise = None
        if rail_paise is not None and rail_paise != locked.amount_paise:
            locked.status = Transaction.Status.FAILED
            locked.failure_reason = "Amount reported by the payment rail does not match"
            locked.completed_at = timezone.now()
            locked.save()
            return locked

    locked.status = result.status
    if locked.status in Transaction.FINAL_STATUSES:
        locked.completed_at = locked.completed_at or timezone.now()
        if locked.status != Transaction.Status.SUCCESS:
            locked.redirect_url = ""

    if locked.status == Transaction.Status.SUCCESS and locked.credited_at is None:
        _credit(locked)

    locked.save()
    return locked


def refresh_transaction(txn: Transaction) -> Transaction:
    """Ask the rail again when the transaction is still pending (UPI, netbanking)."""
    if txn.status != Transaction.Status.PENDING or not txn.rail_transaction_id:
        return txn
    try:
        result = get_rail(txn.method).fetch(txn.rail_transaction_id)
    except (RailUnavailable, RailNotFound):
        return txn
    return apply_outcome(txn, result)


def create_transaction(
    customer: Customer,
    *,
    method: str,
    amount_paise: int,
    reference: str = "",
    description: str = "",
    card: dict | None = None,
    payer_vpa: str = "",
    bank_code: str = "",
    return_url: str = "",
    idempotency_key: str = "",
) -> tuple[Transaction, bool]:
    digest = _request_fingerprint(
        method,
        amount_paise,
        reference,
        card=card,
        payer_vpa=payer_vpa,
        description=description,
        bank_code=bank_code,
        return_url=return_url,
    )
    if idempotency_key:
        existing = Transaction.objects.filter(customer=customer, idempotency_key=idempotency_key).first()
        if existing:
            if existing.request_fingerprint != digest:
                raise IdempotencyConflict
            if existing.status == Transaction.Status.PENDING:
                existing = refresh_transaction(existing)
            return existing, True

    result = _call_rail(
        method,
        _rail_payload(
            method,
            amount_paise,
            reference,
            card=card,
            payer_vpa=payer_vpa,
            description=description,
            bank_code=bank_code,
            return_url=return_url,
        ),
        idempotency_key,
    )

    txn = Transaction(
        id=uuid.uuid4(),
        customer=customer,
        method=method,
        status=Transaction.Status.PENDING,
        amount_paise=amount_paise,
        reference=reference,
        description=description,
        return_url=return_url,
        idempotency_key=idempotency_key,
        request_fingerprint=digest,
    )
    try:
        with transaction.atomic():
            txn.save()
            txn = apply_outcome(txn, result)
    except IntegrityError as error:
        existing = Transaction.objects.filter(customer=customer, idempotency_key=idempotency_key).first()
        if existing and existing.request_fingerprint == digest:
            return existing, True
        if existing:
            raise IdempotencyConflict from error
        raise
    return txn, False


def record_successful_transaction(
    customer: Customer,
    *,
    amount_paise: int,
    reference: str = "",
    method: str = Transaction.Method.CARD,
    instrument: dict | None = None,
) -> Transaction:
    """Record a successful collection and credit unsettled (net of commission). Used by tests and settlement setup."""
    txn = Transaction(
        id=uuid.uuid4(),
        customer=customer,
        method=method,
        status=Transaction.Status.SUCCESS,
        amount_paise=amount_paise,
        reference=reference,
        instrument=instrument or {},
        completed_at=timezone.now(),
    )
    with transaction.atomic():
        txn.save()
        _credit(txn)
        txn.save(update_fields=["credited_at", "commission_rate_bps", "commission_paise"])
    return txn


def settle_customer(
    customer: Customer,
    bank_account: BankAccount,
    amount_paise: int | None = None,
) -> tuple[Wallet, int, Settlement | None]:
    """Settle ``amount_paise`` (default: every unsettled rupee) to one of the customer's accounts.

    Returns ``(wallet, moved_paise, settlement)``. Settling with nothing unsettled
    and no explicit amount moves nothing and returns ``settlement=None``.
    """
    if bank_account.customer_id != customer.id or not bank_account.active:
        raise ValidationError({"bank_account_id": ["No active bank account with that id."]})

    get_or_create_wallet(customer)
    settlement_id = uuid.uuid4()
    try:
        with transaction.atomic():
            wallet, moved = move_to_settled(customer, amount_paise, settlement_id)
            settlement = Settlement.objects.create(
                id=settlement_id,
                customer=customer,
                bank_account=bank_account,
                amount_paise=moved,
                account_holder_name=bank_account.account_holder_name,
                account_last_four=bank_account.last_four,
                ifsc=bank_account.ifsc,
            )
    except NothingToSettle:
        if amount_paise is not None:
            raise ValidationError({"amount": ["amount must be greater than 0"]})
        return get_or_create_wallet(customer), 0, None
    except InsufficientUnsettled as error:
        raise ValidationError(
            {
                "amount": [
                    f"Insufficient unsettled balance. Unsettled: {format_amount(error.unsettled_paise)}, "
                    f"requested: {format_amount(error.requested_paise)}."
                ]
            }
        ) from error
    return wallet, moved, settlement


def _bank_verdict(account: BankAccount, amount_paise: int) -> tuple[bool, str]:
    """Mock transfer. Test accounts fail on purpose so every path can be hit."""
    number = account.account_number()
    if account.ifsc.startswith("FAIL"):
        return False, "Beneficiary bank rejected the transfer"
    if number.endswith("0000"):
        return False, "Account is invalid or closed"
    if amount_paise % 100 == 99:
        return False, "Beneficiary bank rejected the transfer"
    return True, ""


def request_payout(
    customer: Customer,
    *,
    amount_paise: int,
    bank_account: BankAccount,
    idempotency_key: str = "",
) -> tuple[Payout, bool]:
    if bank_account.customer_id != customer.id or not bank_account.active:
        raise ValidationError({"bank_account_id": ["No active bank account with that id."]})
    if amount_paise < MIN_PAYOUT_PAISE:
        raise ValidationError({"amount": [f"amount must be at least {format_amount(MIN_PAYOUT_PAISE)}"]})

    digest = fingerprint(amount_paise, str(bank_account.id))
    if idempotency_key:
        existing = Payout.objects.filter(customer=customer, idempotency_key=idempotency_key).first()
        if existing:
            if existing.request_fingerprint != digest:
                raise IdempotencyConflict
            return existing, True

    payout = Payout(
        id=uuid.uuid4(),
        customer=customer,
        bank_account=bank_account,
        amount_paise=amount_paise,
        status=Payout.Status.FAILED,
        account_holder_name=bank_account.account_holder_name,
        account_last_four=bank_account.last_four,
        ifsc=bank_account.ifsc,
        idempotency_key=idempotency_key,
        request_fingerprint=digest,
        completed_at=timezone.now(),
    )

    try:
        with transaction.atomic():
            try:
                debit_payout(customer, amount_paise, payout.id)
            except InsufficientSettled as error:
                raise ValidationError(
                    {
                        "amount": [
                            f"Insufficient settled balance. Settled: {format_amount(error.settled_paise)}, "
                            f"requested: {format_amount(error.requested_paise)}."
                        ]
                    }
                ) from error

            ok, reason = _bank_verdict(bank_account, amount_paise)
            if ok:
                payout.status = Payout.Status.SUCCESS
                payout.bank_reference = f"AIRP{secrets.randbelow(10**12):012d}"
                payout.failure_reason = ""
            else:
                reverse_payout(customer, amount_paise, payout.id)
                payout.status = Payout.Status.FAILED
                payout.failure_reason = reason
            payout.completed_at = timezone.now()
            payout.save()
    except IntegrityError as error:
        existing = Payout.objects.filter(customer=customer, idempotency_key=idempotency_key).first()
        if existing and existing.request_fingerprint == digest:
            return existing, True
        if existing:
            raise IdempotencyConflict from error
        raise
    return payout, False
