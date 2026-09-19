import logging

from rest_framework import generics

from user_app.context import require_current_user

from .models import Wallet
from .serializers import WalletSerializer

logger = logging.getLogger(__name__)


class WalletView(generics.RetrieveAPIView):
    """GET /api/wallet/ — returns the wallet of the currently logged-in user."""

    serializer_class = WalletSerializer

    def get_object(self) -> Wallet:
        user = require_current_user()
        logger.info(
            "class=WalletView op=get_object message=fetching wallet user_id=%s", user.id
        )
        return Wallet.objects.get(user=user)
