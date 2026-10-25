import re
from urllib.parse import urlparse

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from core.money import MIN_UPI_PAISE, AmountField, format_amount
from payments.commission import format_rate
from payments.models import Payout, Refund, Settlement, Transaction, Wallet


def balance_body(wallet: Wallet, settled_now: int | None = None) -> dict:
    body = {
        "currency": "INR",
        "unsettled": format_amount(wallet.unsettled_paise),
        "settled": format_amount(wallet.settled_paise),
        "total": format_amount(wallet.unsettled_paise + wallet.settled_paise),
    }
    if settled_now is not None:
        body["settled_now"] = format_amount(settled_now)
    return body


class BalanceSerializer(serializers.Serializer):
    currency = serializers.CharField()
    unsettled = serializers.CharField()
    settled = serializers.CharField()
    total = serializers.CharField()


class CreateSettlementSerializer(serializers.Serializer):
    bank_account_id = serializers.UUIDField()
    amount = AmountField(
        required=False,
        help_text='Rupees to settle, such as "500.00". Omit to settle the whole unsettled balance.',
    )


def _snapshot_account(obj) -> dict:
    return {
        "id": str(obj.bank_account_id) if obj.bank_account_id else None,
        "account_holder_name": obj.account_holder_name,
        "account_number_last_four": obj.account_last_four,
        "ifsc": obj.ifsc,
    }


class SettlementSerializer(serializers.ModelSerializer):
    amount = AmountField(source="amount_paise")
    bank_account = serializers.SerializerMethodField()

    class Meta:
        model = Settlement
        fields = ["id", "amount", "bank_account", "created_at"]

    def get_bank_account(self, settlement: Settlement) -> dict:
        return _snapshot_account(settlement)


class SettleResponseSerializer(BalanceSerializer):
    settled_now = serializers.CharField()
    settlement = SettlementSerializer(allow_null=True)


class CardDetailsSerializer(serializers.Serializer):
    card_type = serializers.ChoiceField(choices=["credit", "debit"])
    number = serializers.CharField()
    expiry_month = serializers.IntegerField(min_value=1, max_value=12)
    expiry_year = serializers.IntegerField(min_value=2000, max_value=2100)
    cvv = serializers.RegexField(r"^\d{3,4}$")
    holder_name = serializers.RegexField(r"^[A-Za-z][A-Za-z .'\-]{1,99}$")

    def validate_number(self, value: str) -> str:
        digits = value.replace(" ", "").replace("-", "")
        if not digits.isdigit() or not 13 <= len(digits) <= 19:
            raise serializers.ValidationError("card number must be 13 to 19 digits")
        return digits


class CreateTransactionSerializer(serializers.Serializer):
    ALLOWED = {
        "method",
        "amount",
        "currency",
        "reference",
        "card",
        "payer_vpa",
        "description",
        "bank_code",
        "return_url",
    }

    method = serializers.ChoiceField(choices=Transaction.Method.choices)
    amount = AmountField()
    currency = serializers.ChoiceField(choices=["INR"], required=False, default="INR")
    reference = serializers.RegexField(r"^[A-Za-z0-9_-]{0,64}$", required=False, allow_blank=True, default="")
    card = CardDetailsSerializer(required=False)
    payer_vpa = serializers.CharField(required=False, allow_blank=True, default="")
    description = serializers.CharField(required=False, allow_blank=True, default="", max_length=50)
    bank_code = serializers.CharField(required=False, allow_blank=True, default="")
    return_url = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_payer_vpa(self, value: str) -> str:
        value = value.strip().lower()
        if value and not _VPA.match(value):
            raise serializers.ValidationError("payer_vpa must look like name@handle")
        return value

    def validate_bank_code(self, value: str) -> str:
        value = value.strip().upper()
        if value and not _BANK_CODE.match(value):
            raise serializers.ValidationError("bank_code must be the first four letters of the IFSC")
        return value

    def validate_return_url(self, value: str) -> str:
        value = value.strip()
        if not value:
            return value
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username:
            raise serializers.ValidationError("return_url must be an absolute http or https URL")
        return value

    def validate_description(self, value: str) -> str:
        if any(ord(char) < 32 for char in value):
            raise serializers.ValidationError("description must not contain control characters")
        return value

    def validate(self, attrs):
        unknown = set(getattr(self, "initial_data", {}) or {}) - self.ALLOWED
        if unknown:
            raise serializers.ValidationError({field: ["This field is not allowed."] for field in sorted(unknown)})

        method = attrs["method"]
        if method == Transaction.Method.CARD:
            if not attrs.get("card"):
                raise serializers.ValidationError({"card": ["card is required for CARD payments."]})
            if attrs.get("payer_vpa"):
                raise serializers.ValidationError({"payer_vpa": ["payer_vpa is only used for UPI."]})
            if attrs.get("bank_code") or attrs.get("return_url"):
                raise serializers.ValidationError({"bank_code": ["bank_code is only used for NETBANKING."]})
        elif method == Transaction.Method.UPI:
            if not attrs.get("payer_vpa"):
                raise serializers.ValidationError({"payer_vpa": ["payer_vpa is required for UPI payments."]})
            if attrs.get("card"):
                raise serializers.ValidationError({"card": ["card is only used for CARD payments."]})
            if attrs.get("bank_code") or attrs.get("return_url"):
                raise serializers.ValidationError({"bank_code": ["bank_code is only used for NETBANKING."]})
            if attrs["amount"] < MIN_UPI_PAISE:
                raise serializers.ValidationError({"amount": [f"amount must be at least {format_amount(MIN_UPI_PAISE)}"]})
        else:
            if not attrs.get("bank_code"):
                raise serializers.ValidationError({"bank_code": ["bank_code is required for NETBANKING payments."]})
            if not attrs.get("return_url"):
                raise serializers.ValidationError({"return_url": ["return_url is required for NETBANKING payments."]})
            if attrs.get("card"):
                raise serializers.ValidationError({"card": ["card is only used for CARD payments."]})
            if attrs.get("payer_vpa"):
                raise serializers.ValidationError({"payer_vpa": ["payer_vpa is only used for UPI."]})
        return attrs


class TransactionSerializer(serializers.ModelSerializer):
    amount = AmountField(source="amount_paise")
    credited = serializers.SerializerMethodField()
    commission = AmountField(source="commission_paise")
    commission_rate = serializers.SerializerMethodField()
    net_amount = serializers.SerializerMethodField()
    refunded = AmountField(source="refunded_paise")
    refundable = AmountField(source="refundable_paise")
    refund_status = serializers.SerializerMethodField()

    class Meta:
        model = Transaction
        fields = [
            "id",
            "method",
            "status",
            "amount",
            "currency",
            "reference",
            "description",
            "instrument",
            "rail_transaction_id",
            "rail_reference",
            "redirect_url",
            "failure_reason",
            "failure_code",
            "credited",
            "commission",
            "commission_rate",
            "net_amount",
            "refunded",
            "refundable",
            "refund_status",
            "created_at",
            "completed_at",
        ]

    @extend_schema_field(
        serializers.ChoiceField(
            choices=["NONE", "PARTIAL", "FULL"],
            help_text="`NONE` until a refund succeeds, `PARTIAL` while some is left to refund, `FULL` once all of it is refunded.",
        )
    )
    def get_refund_status(self, txn: Transaction) -> str:
        if txn.refunded_paise == 0:
            return "NONE"
        return "FULL" if txn.refunded_paise >= txn.amount_paise else "PARTIAL"

    def get_credited(self, txn: Transaction) -> bool:
        return txn.credited_at is not None

    @extend_schema_field(serializers.CharField(help_text='Commission rate in percent, such as "1.00".'))
    def get_commission_rate(self, txn: Transaction) -> str:
        return format_rate(txn.commission_rate_bps)

    @extend_schema_field(
        serializers.CharField(
            allow_null=True,
            help_text="Amount minus commission, added to the unsettled balance. Null until the payment succeeds.",
        )
    )
    def get_net_amount(self, txn: Transaction) -> str | None:
        return format_amount(txn.net_paise) if txn.credited_at is not None else None


class CreatePayoutSerializer(serializers.Serializer):
    amount = AmountField()
    bank_account_id = serializers.UUIDField()


class PayoutSerializer(serializers.ModelSerializer):
    amount = AmountField(source="amount_paise")
    bank_account = serializers.SerializerMethodField()

    class Meta:
        model = Payout
        fields = [
            "id",
            "amount",
            "status",
            "bank_account",
            "bank_reference",
            "failure_reason",
            "created_at",
            "completed_at",
        ]

    def get_bank_account(self, payout: Payout) -> dict:
        return {
            "id": str(payout.bank_account_id) if payout.bank_account_id else None,
            "account_holder_name": payout.account_holder_name,
            "account_number_last_four": payout.account_last_four,
            "ifsc": payout.ifsc,
        }


class CreateRefundSerializer(serializers.Serializer):
    amount = AmountField(
        required=False,
        help_text='Rupees to refund, such as "250.00". Omit to refund everything not yet refunded.',
    )
    reason = serializers.CharField(required=False, allow_blank=True, default="", max_length=200)

    def validate_reason(self, value: str) -> str:
        value = value.strip()
        if any(ord(char) < 32 for char in value):
            raise serializers.ValidationError("reason must not contain control characters")
        return value


class RefundTransactionSerializer(serializers.ModelSerializer):
    """The payment a refund belongs to, in short."""

    amount = AmountField(source="amount_paise")

    class Meta:
        model = Transaction
        fields = ["id", "method", "amount", "reference", "instrument"]


class RefundSerializer(serializers.ModelSerializer):
    transaction_id = serializers.UUIDField(read_only=True)
    transaction = RefundTransactionSerializer(read_only=True)
    amount = AmountField(source="amount_paise")
    commission_returned = AmountField(source="commission_returned_paise")
    net_debit = serializers.SerializerMethodField()

    class Meta:
        model = Refund
        fields = [
            "id",
            "transaction_id",
            "transaction",
            "amount",
            "commission_returned",
            "net_debit",
            "status",
            "reason",
            "failure_reason",
            "reference",
            "created_at",
            "completed_at",
        ]

    @extend_schema_field(
        serializers.CharField(help_text="What left the wallet: the refund minus the commission AirPay returned.")
    )
    def get_net_debit(self, refund: Refund) -> str:
        return format_amount(refund.net_debit_paise) if refund.status == Refund.Status.SUCCESS else "0.00"


_VPA = re.compile(r"^[a-z0-9._-]{2,256}@[a-z]{2,64}$")
_BANK_CODE = re.compile(r"^[A-Z]{4}$")
