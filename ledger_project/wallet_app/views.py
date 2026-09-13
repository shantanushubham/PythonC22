from rest_framework import generics

from user_app.context import require_current_user

from .models import Wallet
from .serializers import WalletSerializer


class WalletView(generics.RetrieveAPIView):
    """GET /api/wallet/ — returns the wallet of the currently logged-in user."""

    serializer_class = WalletSerializer

    def get_object(self) -> Wallet:
        user = require_current_user()
        return Wallet.objects.get(user=user)
