import logging

from django.db import transaction

from rest_framework import serializers

from bank_account_app.models import BankAccount
from bank_txn_app.gateway import PaymentGatewayError, create_bank_transaction
from bank_txn_app.models import BankTxn
from wallet_app.models import Wallet

from .models import Txn

from .tasks import send_notification_sms, send_notification_email

logger = logging.getLogger(__name__)


class TxnSerializer(serializers.ModelSerializer):

    # Write-only, not a field on Txn itself. Required whenever the txn has a
    # bank leg (i.e. sender_wallet or receiver_wallet is null) — that's when
    # a BankTxn record needs to be created against a specific bank account.
    bank_account = serializers.PrimaryKeyRelatedField(
        queryset=BankAccount.objects.all(), write_only=True, required=False
    )

    class Meta:
        model = Txn
        fields = [
            "id",
            "amount",
            "sender_wallet",
            "receiver_wallet",
            "bank_account",
            "is_success",
            "created_at",
        ]
        read_only_fields = ["id", "is_success", "created_at"]

    def validate(self, attrs):
        sender: Wallet | None = attrs.get("sender_wallet")
        receiver: Wallet | None = attrs.get("receiver_wallet")
        bank_account: BankAccount | None = attrs.get("bank_account")

        if sender is None and receiver is None:
            logger.warning(
                "class=TxnSerializer op=validate message=neither sender_wallet nor receiver_wallet provided"
            )
            raise serializers.ValidationError(
                "At least one of sender_wallet or receiver_wallet must be provided."
            )

        if sender is not None and sender == receiver:
            logger.warning(
                "class=TxnSerializer op=validate message=sender_wallet and receiver_wallet are the same "
                "sender_id=%s",
                sender.id,
            )
            raise serializers.ValidationError(
                "sender_wallet and receiver_wallet cannot be the same."
            )

        amount = attrs.get("amount", 0)
        if amount <= 0:
            logger.info(
                "class=TxnSerializer op=validate message=amount is not positive amount=%s",
                amount,
            )
            raise serializers.ValidationError("amount must be greater than 0.")

        if sender is not None and sender.balance < amount:
            logger.warning(
                "class=TxnSerializer op=validate message=insufficient balance "
                "sender_id=%s balance=%s amount=%s",
                sender.id,
                sender.balance,
                amount,
            )
            raise serializers.ValidationError(
                "sender_wallet does not have sufficient balance for this transaction."
            )

        # A bank leg exists whenever exactly one of sender/receiver is null
        # (load: sender is null, withdraw: receiver is null). Wallet-to-wallet
        # transfers have both set and never touch a bank account.
        involves_bank = sender is None or receiver is None

        if involves_bank and bank_account is None:
            raise serializers.ValidationError(
                "bank_account is required when loading money from, or sending "
                "money to, a bank account."
            )

        if not involves_bank and bank_account is not None:
            raise serializers.ValidationError(
                "bank_account should not be provided for wallet-to-wallet transfers."
            )

        if bank_account is not None:
            request = self.context.get("request")
            if request is not None and bank_account.user_id != request.user.id:
                raise serializers.ValidationError(
                    "bank_account does not belong to the logged-in user."
                )

        return attrs

    def create(self, validated_data):
        bank_account: BankAccount | None = validated_data.pop("bank_account", None)
        sender: Wallet | None = validated_data.get("sender_wallet")
        receiver: Wallet | None = validated_data.get("receiver_wallet")
        amount = validated_data["amount"]

        # Call the payment gateway *before* opening a DB transaction — it's a
        # network call and shouldn't hold a DB transaction open.
        gateway_data = None
        if bank_account is not None:
            # sender is None   -> Load (bank -> wallet)     -> money leaves the bank -> debit
            # receiver is None -> Withdraw (wallet -> bank)  -> money enters the bank -> credit
            transaction_type = "debit" if sender is None else "credit"

            logger.info(
                "class=TxnSerializer op=create message=calling payment gateway "
                "bank_account_id=%s type=%s amount=%s",
                bank_account.id,
                transaction_type,
                amount,
            )
            try:
                gateway_data = create_bank_transaction(
                    account_no=bank_account.account_no,
                    ifsc_code=bank_account.ifsc_code,
                    account_name=bank_account.account_name,
                    bank_name=bank_account.bank_name,
                    transaction_type=transaction_type,
                    amount=amount,
                )
            except PaymentGatewayError as exc:
                logger.error(
                    "class=TxnSerializer op=create message=payment gateway error "
                    "bank_account_id=%s error=%s",
                    bank_account.id,
                    exc,
                )
                raise serializers.ValidationError(
                    f"Payment gateway error: {exc}"
                ) from exc

        # 200 (SUCCESS) and 402 (bank-declined FAILED) are both legitimate
        # completed gateway calls — is_success reflects the actual outcome.
        gateway_success = gateway_data is None or gateway_data["status"] == "SUCCESS"

        with transaction.atomic():
            txn = Txn.objects.create(**validated_data, is_success=gateway_success)

            # Only move wallet money if the transaction actually succeeded.
            if gateway_success:
                if sender is not None:
                    sender.balance -= amount
                    sender.save(update_fields=["balance", "updated_at"])

                if receiver is not None:
                    receiver.balance += amount
                    receiver.save(update_fields=["balance", "updated_at"])

            if bank_account is not None:
                BankTxn.objects.create(
                    txn=txn,
                    bank_account=bank_account,
                    gateway_reference_id=gateway_data.get("transactionId"),
                    status=(
                        BankTxn.Status.SUCCESS
                        if gateway_success
                        else BankTxn.Status.FAILED
                    ),
                    failure_reason=gateway_data.get("failureReason"),
                )

        logger.info(
            "class=TxnSerializer op=create message=txn created txn_id=%s is_success=%s amount=%s",
            txn.id,
            gateway_success,
            amount,
        )
        send_notification_sms.delay(
            sender.user.phone_number, f"Transaction successful for amount {amount}"
        )
        send_notification_email.delay(
            sender.user.email, f"Transaction successful for amount {amount}"
        )
        return txn


# Create Txn
# Debit Money from Sender - SUCCESS | 1000 -> 500
# Credit Money to Reciever - FAILS
# If Bank Txn then save
