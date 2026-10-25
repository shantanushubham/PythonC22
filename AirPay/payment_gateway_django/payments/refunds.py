"""Refunds: money returned to the payer for a collected transaction.

How it works
------------
* Only a ``SUCCESS`` transaction whose wallet credit was made can be refunded, up to the
  amount not yet refunded. Several partial refunds are allowed.
* The refund comes out of the customer's wallet: unsettled first, then settled. If the
  customer no longer has the money (it was paid out), the refund is refused.
* AirPay gives back its commission in proportion to what is refunded (``commission_to_return``),
  so a full refund leaves the wallet where it was before the payment.
* The payer's bank is a mock, like the bank in ``request_payout``: ``_processor_verdict`` decides.
  A refund that fails moves no money and does not use up any of the refundable amount.

To use a real rail later, replace ``_processor_verdict`` with a call to the rail. It has to run
*before* the wallet is debited, and a failure must leave the wallet alone, as it does here.
"""

from __future__ import annotations

import secrets
import uuid

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from core.money import format_amount
from customers.models import Customer
from payments.idempotency import fingerprint
from payments.models import Refund, Transaction
from payments.services import IdempotencyConflict
from payments.wallet import InsufficientForRefund, debit_refund


class NotRefundable(Exception):
    """The transaction cannot be refunded at all (not collected, or nothing left)."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def commission_to_return(txn: Transaction, amount_paise: int) -> int:
    """The share of AirPay's commission given back for a refund of ``amount_paise``.

    The share is worked out on the running total refunded, rounded half up, minus what was
    already returned. Rounding therefore never drifts: when the whole amount has been
    refunded, exactly the whole commission has been returned, however it was split.
    """
    if txn.commission_paise == 0:
        return 0
    cumulative = txn.refunded_paise + amount_paise
    due = (2 * txn.commission_paise * cumulative + txn.amount_paise) // (2 * txn.amount_paise)
    return max(0, min(due - txn.commission_refunded_paise, txn.commission_paise - txn.commission_refunded_paise))


def _processor_verdict(txn: Transaction, amount_paise: int) -> tuple[bool, str]:
    """Mock refund processor. A refund ending in 99 paise is declined, so the failure path can be tested."""
    if amount_paise % 100 == 99:
        return False, "The payer's bank could not process the refund"
    return True, ""


def request_refund(
    customer: Customer,
    transaction_id,
    *,
    amount_paise: int | None = None,
    reason: str = "",
    idempotency_key: str = "",
) -> tuple[Refund, bool]:
    """Refund ``amount_paise`` (default: everything not yet refunded). Returns ``(refund, replayed)``."""
    digest = fingerprint(str(transaction_id), amount_paise, reason)
    if idempotency_key:
        existing = Refund.objects.filter(customer=customer, idempotency_key=idempotency_key).first()
        if existing:
            if existing.request_fingerprint != digest:
                raise IdempotencyConflict
            return existing, True

    try:
        with transaction.atomic():
            # Lock the transaction first, then the wallet (inside debit_refund). apply_outcome uses
            # the same order, so the two cannot deadlock.
            txn = Transaction.objects.select_for_update().filter(pk=transaction_id, customer=customer).first()
            if txn is None:
                raise Transaction.DoesNotExist
            if txn.status != Transaction.Status.SUCCESS or txn.credited_at is None:
                raise NotRefundable("Only a successful payment can be refunded.")
            remaining = txn.refundable_paise
            if remaining <= 0:
                raise NotRefundable("This payment has already been refunded in full.")

            amount = remaining if amount_paise is None else amount_paise
            if amount > remaining:
                raise ValidationError(
                    {
                        "amount": [
                            f"Cannot refund more than is left to refund. "
                            f"Refundable: {format_amount(remaining)}, requested: {format_amount(amount)}."
                        ]
                    }
                )

            ok, failure_reason = _processor_verdict(txn, amount)
            refund = Refund(
                id=uuid.uuid4(),
                customer=customer,
                transaction=txn,
                amount_paise=amount,
                reason=reason,
                idempotency_key=idempotency_key,
                request_fingerprint=digest,
                completed_at=timezone.now(),
            )
            if not ok:
                refund.status = Refund.Status.FAILED
                refund.failure_reason = failure_reason
                refund.save()
                return refund, False

            returned = commission_to_return(txn, amount)
            try:
                debit_refund(customer, amount, returned, refund.id)
            except InsufficientForRefund as error:
                raise ValidationError(
                    {
                        "amount": [
                            "Not enough balance to refund this. "
                            f"Your balance: {format_amount(error.available_paise)}, "
                            f"this refund takes {format_amount(error.needed_paise)}."
                        ]
                    }
                ) from error

            refund.status = Refund.Status.SUCCESS
            refund.commission_returned_paise = returned
            refund.reference = f"AIRR{secrets.randbelow(10**12):012d}"
            refund.save()
            txn.refunded_paise += amount
            txn.commission_refunded_paise += returned
            txn.save(update_fields=["refunded_paise", "commission_refunded_paise", "updated_at"])
            return refund, False
    except IntegrityError as error:
        # Two requests with the same Idempotency-Key at the same moment. The database decides.
        existing = Refund.objects.filter(customer=customer, idempotency_key=idempotency_key).first() if idempotency_key else None
        if existing and existing.request_fingerprint == digest:
            return existing, True
        if existing:
            raise IdempotencyConflict from error
        raise
