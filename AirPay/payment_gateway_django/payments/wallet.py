"""The only place wallet balances change.

Every credit and debit writes a ledger row and updates Wallet in the same
transaction, under ``select_for_update``. Two payouts for the same rupee cannot
both succeed.
"""

from __future__ import annotations

from uuid import uuid4

from django.db import transaction

from customers.models import Customer
from payments.models import LedgerEntry, Wallet


class InsufficientSettled(Exception):
    def __init__(self, settled_paise: int, requested_paise: int):
        self.settled_paise = settled_paise
        self.requested_paise = requested_paise
        super().__init__("Insufficient settled balance")


class InsufficientUnsettled(Exception):
    def __init__(self, unsettled_paise: int, requested_paise: int):
        self.unsettled_paise = unsettled_paise
        self.requested_paise = requested_paise
        super().__init__("Insufficient unsettled balance")


class NothingToSettle(Exception):
    pass


class InsufficientForRefund(Exception):
    def __init__(self, available_paise: int, needed_paise: int):
        self.available_paise = available_paise
        self.needed_paise = needed_paise
        super().__init__("Insufficient balance for the refund")


def get_or_create_wallet(customer: Customer) -> Wallet:
    wallet, _ = Wallet.objects.get_or_create(customer=customer)
    return wallet


def _locked(customer: Customer) -> Wallet:
    get_or_create_wallet(customer)
    return Wallet.objects.select_for_update().get(customer=customer)


def _write(
    wallet: Wallet,
    *,
    amount_paise: int,
    bucket: str,
    direction: str,
    kind: str,
    reference_type: str,
    reference_id,
) -> LedgerEntry:
    if amount_paise <= 0:
        raise ValueError("ledger amounts must be greater than 0")

    if direction == LedgerEntry.Direction.CREDIT:
        if bucket == LedgerEntry.Bucket.UNSETTLED:
            wallet.unsettled_paise += amount_paise
        else:
            wallet.settled_paise += amount_paise
    else:
        if bucket == LedgerEntry.Bucket.UNSETTLED:
            if wallet.unsettled_paise < amount_paise:
                raise RuntimeError("unsettled balance would go negative")
            wallet.unsettled_paise -= amount_paise
        else:
            if wallet.settled_paise < amount_paise:
                raise InsufficientSettled(wallet.settled_paise, amount_paise)
            wallet.settled_paise -= amount_paise

    wallet.save(update_fields=["unsettled_paise", "settled_paise", "updated_at"])
    return LedgerEntry.objects.create(
        customer=wallet.customer,
        amount_paise=amount_paise,
        bucket=bucket,
        direction=direction,
        kind=kind,
        reference_type=reference_type,
        reference_id=reference_id,
    )


@transaction.atomic
def credit_collection(customer: Customer, amount_paise: int, payment_id, commission_paise: int = 0) -> Wallet:
    """Credit a collection to unsettled, then take AirPay's commission out of it.

    Two ledger rows, so the books show both the gross collection and the fee.
    The customer is left with ``amount_paise - commission_paise`` unsettled.
    """
    if not 0 <= commission_paise < amount_paise:
        raise ValueError("commission must be at least 0 and less than the collected amount")
    wallet = _locked(customer)
    _write(
        wallet,
        amount_paise=amount_paise,
        bucket=LedgerEntry.Bucket.UNSETTLED,
        direction=LedgerEntry.Direction.CREDIT,
        kind=LedgerEntry.Kind.COLLECTION,
        reference_type="transaction",
        reference_id=payment_id,
    )
    if commission_paise:
        _write(
            wallet,
            amount_paise=commission_paise,
            bucket=LedgerEntry.Bucket.UNSETTLED,
            direction=LedgerEntry.Direction.DEBIT,
            kind=LedgerEntry.Kind.COMMISSION,
            reference_type="transaction",
            reference_id=payment_id,
        )
    return wallet


@transaction.atomic
def settle(
    customer: Customer,
    amount_paise: int | None = None,
    settlement_id=None,
) -> tuple[Wallet, int]:
    """Move unsettled funds to settled. ``amount_paise`` defaults to all unsettled."""
    wallet = _locked(customer)
    moving = wallet.unsettled_paise if amount_paise is None else amount_paise
    if moving <= 0:
        raise NothingToSettle
    if moving > wallet.unsettled_paise:
        raise InsufficientUnsettled(wallet.unsettled_paise, moving)

    settlement_id = settlement_id or uuid4()
    _write(
        wallet,
        amount_paise=moving,
        bucket=LedgerEntry.Bucket.UNSETTLED,
        direction=LedgerEntry.Direction.DEBIT,
        kind=LedgerEntry.Kind.SETTLEMENT,
        reference_type="settlement",
        reference_id=settlement_id,
    )
    _write(
        wallet,
        amount_paise=moving,
        bucket=LedgerEntry.Bucket.SETTLED,
        direction=LedgerEntry.Direction.CREDIT,
        kind=LedgerEntry.Kind.SETTLEMENT,
        reference_type="settlement",
        reference_id=settlement_id,
    )
    return wallet, moving


@transaction.atomic
def debit_payout(customer: Customer, amount_paise: int, payout_id) -> Wallet:
    wallet = _locked(customer)
    _write(
        wallet,
        amount_paise=amount_paise,
        bucket=LedgerEntry.Bucket.SETTLED,
        direction=LedgerEntry.Direction.DEBIT,
        kind=LedgerEntry.Kind.PAYOUT,
        reference_type="payout",
        reference_id=payout_id,
    )
    return wallet


@transaction.atomic
def reverse_payout(customer: Customer, amount_paise: int, payout_id) -> Wallet:
    wallet = _locked(customer)
    _write(
        wallet,
        amount_paise=amount_paise,
        bucket=LedgerEntry.Bucket.SETTLED,
        direction=LedgerEntry.Direction.CREDIT,
        kind=LedgerEntry.Kind.PAYOUT_REVERSAL,
        reference_type="payout",
        reference_id=payout_id,
    )
    return wallet


@transaction.atomic
def debit_refund(customer: Customer, amount_paise: int, commission_returned_paise: int, refund_id) -> Wallet:
    """Take a refund out of the wallet. AirPay's returned commission is credited back first.

    The customer pays ``amount - commission_returned`` in net. It comes out of unsettled
    first, then settled. If both together are not enough, nothing changes and
    ``InsufficientForRefund`` is raised.
    """
    if not 0 <= commission_returned_paise <= amount_paise:
        raise ValueError("returned commission must be between 0 and the refund amount")
    wallet = _locked(customer)
    needed = amount_paise - commission_returned_paise
    available = wallet.unsettled_paise + wallet.settled_paise
    if available < needed:
        raise InsufficientForRefund(available, needed)

    if commission_returned_paise:
        _write(
            wallet,
            amount_paise=commission_returned_paise,
            bucket=LedgerEntry.Bucket.UNSETTLED,
            direction=LedgerEntry.Direction.CREDIT,
            kind=LedgerEntry.Kind.COMMISSION_REVERSAL,
            reference_type="refund",
            reference_id=refund_id,
        )
    # After the credit above, unsettled + settled >= amount, so the rest always fits.
    from_unsettled = min(wallet.unsettled_paise, amount_paise)
    if from_unsettled:
        _write(
            wallet,
            amount_paise=from_unsettled,
            bucket=LedgerEntry.Bucket.UNSETTLED,
            direction=LedgerEntry.Direction.DEBIT,
            kind=LedgerEntry.Kind.REFUND,
            reference_type="refund",
            reference_id=refund_id,
        )
    from_settled = amount_paise - from_unsettled
    if from_settled:
        _write(
            wallet,
            amount_paise=from_settled,
            bucket=LedgerEntry.Bucket.SETTLED,
            direction=LedgerEntry.Direction.DEBIT,
            kind=LedgerEntry.Kind.REFUND,
            reference_type="refund",
            reference_id=refund_id,
        )
    return wallet


def ledger_totals(customer: Customer) -> tuple[int, int]:
    """Recompute both balances from the ledger. Used to check the wallet is honest."""
    unsettled = settled = 0
    for entry in LedgerEntry.objects.filter(customer=customer):
        signed = entry.amount_paise if entry.direction == LedgerEntry.Direction.CREDIT else -entry.amount_paise
        if entry.bucket == LedgerEntry.Bucket.UNSETTLED:
            unsettled += signed
        else:
            settled += signed
    return unsettled, settled
