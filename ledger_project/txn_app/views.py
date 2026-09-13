from rest_framework import mixins
from rest_framework.viewsets import GenericViewSet

from user_app.context import require_current_user

from .models import Txn
from .serializers import TxnSerializer


class TxnViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    GenericViewSet,
):
    """
    Transactions are immutable once created — no update or delete.

      list     GET  /api/txns/        All txns where logged-in user's wallet is sender OR receiver
      create   POST /api/txns/        Record a new transaction. Pass `bank_account` when
                                       loading from, or sending to, a bank account — a
                                       matching BankTxn row is created automatically.
      retrieve GET  /api/txns/{id}/   Fetch one transaction by UUID
    """

    serializer_class = TxnSerializer

    def get_queryset(self):
        user = require_current_user()
        wallet = user.wallet  # OneToOne reverse — raises RelatedObjectDoesNotExist if missing
        return Txn.objects.filter(
            sender_wallet=wallet
        ) | Txn.objects.filter(receiver_wallet=wallet)
        # SELECT * FROM wallet WHERE sender_wallet_id=wallet.id OR receiver_wallet_id=wallet.id
