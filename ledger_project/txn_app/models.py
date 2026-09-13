import uuid

from django.db import models

from wallet_app.models import Wallet


class Txn(models.Model):
    """
    Ledger transaction on a wallet.

    Two nullable wallet FKs cover all three movement directions:

      Load  (bank → wallet) : sender_wallet=NULL, receiver_wallet=<wallet>
      Withdraw (wallet → bank) : sender_wallet=<wallet>, receiver_wallet=NULL
      Transfer (wallet → wallet) : both set
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    sender_wallet = models.ForeignKey(
        Wallet,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sent_txns",
    )
    receiver_wallet = models.ForeignKey(
        Wallet,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="received_txns",
    )

    # True = SUCCESS, False = FAILED
    is_success = models.BooleanField(default=False)

    def __str__(self) -> str:
        return (
            f"Txn({self.id} | ₹{self.amount} | "
            f"{'SUCCESS' if self.is_success else 'FAILED'})"
        )
