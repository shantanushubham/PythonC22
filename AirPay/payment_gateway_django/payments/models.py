import uuid

from django.db import models

from customers.models import BankAccount, Customer


class Wallet(models.Model):
    """The two balances AirPay always knows for a customer.

    ``unsettled_paise`` is money from successful AirPay transactions that is not
    yet available to pay out. ``settled_paise`` is available for a bank transfer. Both are
    whole paise. They change only inside ``payments.wallet`` under a row lock.
    """

    customer = models.OneToOneField(Customer, on_delete=models.CASCADE, related_name="wallet")
    unsettled_paise = models.BigIntegerField(default=0)
    settled_paise = models.BigIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(unsettled_paise__gte=0), name="wallet_unsettled_nonneg"),
            models.CheckConstraint(condition=models.Q(settled_paise__gte=0), name="wallet_settled_nonneg"),
        ]

    def __str__(self):
        return f"{self.customer_id} unsettled={self.unsettled_paise} settled={self.settled_paise}"


class LedgerEntry(models.Model):
    """One movement of money. The running balances on Wallet must match these rows."""

    class Bucket(models.TextChoices):
        UNSETTLED = "UNSETTLED"
        SETTLED = "SETTLED"

    class Direction(models.TextChoices):
        CREDIT = "CREDIT"
        DEBIT = "DEBIT"

    class Kind(models.TextChoices):
        COLLECTION = "COLLECTION"
        SETTLEMENT = "SETTLEMENT"
        PAYOUT = "PAYOUT"
        PAYOUT_REVERSAL = "PAYOUT_REVERSAL"
        COMMISSION = "COMMISSION"
        REFUND = "REFUND"
        COMMISSION_REVERSAL = "COMMISSION_REVERSAL"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="ledger_entries")
    amount_paise = models.BigIntegerField()
    bucket = models.CharField(max_length=16, choices=Bucket.choices)
    direction = models.CharField(max_length=8, choices=Direction.choices)
    kind = models.CharField(max_length=24, choices=Kind.choices)
    reference_type = models.CharField(max_length=32)
    reference_id = models.UUIDField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["customer", "-created_at"]),
            models.Index(fields=["reference_type", "reference_id"]),
        ]


class Settlement(models.Model):
    """One settlement: an amount the customer chose to move from unsettled to settled.

    The customer picks which of their bank accounts it is settled to and how much.
    The ledger rows for the move use this row's id as ``reference_id``.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="settlements")
    bank_account = models.ForeignKey(
        BankAccount, on_delete=models.SET_NULL, null=True, related_name="settlements"
    )
    amount_paise = models.BigIntegerField()
    # Snapshot so a later revoke of the account does not hide where the money was settled.
    account_holder_name = models.CharField(max_length=150)
    account_last_four = models.CharField(max_length=4)
    ifsc = models.CharField(max_length=11)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["customer", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.customer_id} settled {self.amount_paise} to …{self.account_last_four}"


class Transaction(models.Model):
    """A payment through AirPay (card, UPI or netbanking).

    Only ``SUCCESS`` credits the customer's unsettled wallet. Payouts are a
    different thing: they are bank transfers out of the settled balance.
    """

    class Method(models.TextChoices):
        CARD = "CARD"
        UPI = "UPI"
        NETBANKING = "NETBANKING"

    class Status(models.TextChoices):
        PENDING = "PENDING"
        SUCCESS = "SUCCESS"
        FAILED = "FAILED"
        EXPIRED = "EXPIRED"
        CANCELLED = "CANCELLED"

    FINAL_STATUSES = frozenset({Status.SUCCESS, Status.FAILED, Status.EXPIRED, Status.CANCELLED})

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="transactions")
    method = models.CharField(max_length=16, choices=Method.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    amount_paise = models.BigIntegerField()
    currency = models.CharField(max_length=3, default="INR")
    reference = models.CharField(max_length=64, blank=True, default="")
    description = models.CharField(max_length=50, blank=True, default="")
    return_url = models.CharField(max_length=500, blank=True, default="")
    redirect_url = models.CharField(max_length=500, blank=True, default="")
    rail_transaction_id = models.CharField(max_length=80, blank=True, default="")
    rail_reference = models.CharField(max_length=40, blank=True, default="")
    instrument = models.JSONField(default=dict)
    failure_reason = models.CharField(max_length=200, blank=True, default="")
    failure_code = models.CharField(max_length=40, blank=True, default="")
    credited_at = models.DateTimeField(null=True, blank=True)
    # Fixed when the wallet is credited. Rate in basis points (100 = 1%).
    commission_rate_bps = models.PositiveIntegerField(default=0)
    commission_paise = models.BigIntegerField(default=0)
    # Running totals of successful refunds. They change only in payments.refunds, under the row lock.
    refunded_paise = models.BigIntegerField(default=0)
    commission_refunded_paise = models.BigIntegerField(default=0)
    idempotency_key = models.CharField(max_length=255, blank=True, default="")
    request_fingerprint = models.CharField(max_length=64, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    @property
    def net_paise(self) -> int:
        """What the customer keeps after AirPay's commission."""
        return self.amount_paise - self.commission_paise

    @property
    def refundable_paise(self) -> int:
        """How much can still be refunded. Only a collected (credited) payment can be refunded."""
        if self.status != self.Status.SUCCESS or self.credited_at is None:
            return 0
        return self.amount_paise - self.refunded_paise

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["customer", "idempotency_key"],
                condition=~models.Q(idempotency_key=""),
                name="unique_transaction_idempotency_key",
            ),
            models.CheckConstraint(
                condition=models.Q(refunded_paise__gte=0, refunded_paise__lte=models.F("amount_paise")),
                name="transaction_refunded_within_amount",
            ),
            models.CheckConstraint(
                condition=models.Q(commission_refunded_paise__gte=0, commission_refunded_paise__lte=models.F("commission_paise")),
                name="transaction_commission_refunded_within_commission",
            ),
        ]
        indexes = [
            models.Index(fields=["customer", "-created_at"]),
            models.Index(fields=["rail_transaction_id"]),
        ]


class Payout(models.Model):
    """A bank transfer of settled funds to one of the customer's accounts."""

    class Status(models.TextChoices):
        SUCCESS = "SUCCESS"
        FAILED = "FAILED"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="payouts")
    bank_account = models.ForeignKey(
        BankAccount, on_delete=models.SET_NULL, null=True, related_name="payouts"
    )
    amount_paise = models.BigIntegerField()
    status = models.CharField(max_length=16, choices=Status.choices)
    failure_reason = models.CharField(max_length=200, blank=True, default="")
    bank_reference = models.CharField(max_length=40, blank=True, default="")
    # Snapshot so a later revoke of the account does not hide where the money went.
    account_holder_name = models.CharField(max_length=150)
    account_last_four = models.CharField(max_length=4)
    ifsc = models.CharField(max_length=11)
    idempotency_key = models.CharField(max_length=255, blank=True, default="")
    request_fingerprint = models.CharField(max_length=64, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["customer", "idempotency_key"],
                condition=~models.Q(idempotency_key=""),
                name="unique_payout_idempotency_key",
            ),
        ]


class Refund(models.Model):
    """Money returned to the payer for a collected transaction.

    A refund is taken out of the customer's wallet (unsettled first, then settled). AirPay
    gives back its commission in proportion to the amount refunded, so a full refund leaves
    the customer's wallet where it was before the payment. ``commission_returned_paise`` is
    that share. A FAILED refund moves no money.
    """

    class Status(models.TextChoices):
        SUCCESS = "SUCCESS"
        FAILED = "FAILED"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="refunds")
    transaction = models.ForeignKey(Transaction, on_delete=models.PROTECT, related_name="refunds")
    amount_paise = models.BigIntegerField()
    commission_returned_paise = models.BigIntegerField(default=0)
    status = models.CharField(max_length=16, choices=Status.choices)
    reason = models.CharField(max_length=200, blank=True, default="")
    failure_reason = models.CharField(max_length=200, blank=True, default="")
    reference = models.CharField(max_length=40, blank=True, default="")
    idempotency_key = models.CharField(max_length=255, blank=True, default="")
    request_fingerprint = models.CharField(max_length=64, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    @property
    def net_debit_paise(self) -> int:
        """What leaves the customer's wallet: the refund minus the commission AirPay gives back."""
        return self.amount_paise - self.commission_returned_paise

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["customer", "idempotency_key"],
                condition=~models.Q(idempotency_key=""),
                name="unique_refund_idempotency_key",
            ),
            models.CheckConstraint(condition=models.Q(amount_paise__gt=0), name="refund_amount_positive"),
        ]
        indexes = [
            models.Index(fields=["customer", "-created_at"]),
            models.Index(fields=["transaction", "-created_at"]),
        ]
