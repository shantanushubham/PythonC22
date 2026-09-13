from django.db import transaction

from rest_framework import serializers

from bank_account_app.models import BankAccount
from user_app.context import require_current_user
from wallet_app.models import Wallet

from .models import Txn


class TxnSerializer(serializers.ModelSerializer):

    # Write-only, not a field on Txn itself. Required whenever the txn has a
    # bank leg (i.e. sender_wallet or receiver_wallet is null) — that's when
    # a BankTxn record needs to be created against a specific bank account.
    bank_account = serializers.PrimaryKeyRelatedField(
        queryset=BankAccount.objects.all(),
        write_only=True,
        required=False,
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
            raise serializers.ValidationError(
                "At least one of sender_wallet or receiver_wallet must be provided."
            )

        if sender is not None and sender == receiver:
            raise serializers.ValidationError(
                "sender_wallet and receiver_wallet cannot be the same."
            )

        amount = attrs.get("amount", 0)
        if amount <= 0:
            raise serializers.ValidationError("amount must be greater than 0.")

        if sender is not None and sender.balance < amount:
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
        bank_account = validated_data.pop("bank_account", None)
        sender = validated_data.get("sender_wallet")
        receiver = validated_data.get("receiver_wallet")
        amount = validated_data["amount"]

        with transaction.atomic():
            txn = Txn.objects.create(**validated_data, is_success=True)

            if sender is not None:
                sender.balance -= amount
                sender.save(update_fields=["balance", "updated_at"])

            if receiver is not None:
                receiver.balance += amount
                receiver.save(update_fields=["balance", "updated_at"])

            if bank_account is not None:
                # TODO: call the payment gateway's REST API here to actually
                # initiate the bank-side transfer (load or withdraw). The
                # gateway would confirm success/failure asynchronously (e.g.
                # via webhook), at which point BankTxn.status (and possibly
                # Txn.is_success) should be updated accordingly. For now the
                # BankTxn is recorded as PENDING with no gateway call made.
                from bank_txn_app.models import BankTxn

                BankTxn.objects.create(txn=txn, bank_account=bank_account, status=BankTxn.Status.SUCCESS)

        return txn
