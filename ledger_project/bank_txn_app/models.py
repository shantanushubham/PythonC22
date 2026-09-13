from django.db import models

from bank_account_app.models import BankAccount
from txn_app.models import Txn


class BankTxn(models.Model):
    """
    Bank-side record of a wallet transaction, tied to one bank account.

    Created (1:1) whenever a Txn has a bank leg, i.e. either:
      Load  (bank → wallet) : Txn.sender_wallet   is NULL
      Withdraw (wallet → bank) : Txn.receiver_wallet is NULL

    Wallet-to-wallet transfers (both wallets set on the Txn) never get a
    BankTxn — there's no bank involved.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        SUCCESS = "SUCCESS", "Success"
        FAILED = "FAILED", "Failed"

    txn = models.OneToOneField(Txn, on_delete=models.CASCADE, related_name="bank_txn")
    bank_account = models.ForeignKey(
        BankAccount, on_delete=models.PROTECT, related_name="bank_txns"
    )

    # Populated once the payment-gateway call is actually wired up.
    gateway_reference_id = models.CharField(max_length=64, null=True, blank=True)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"BankTxn(txn={self.txn_id} | bank_account={self.bank_account_id} | {self.status})"
