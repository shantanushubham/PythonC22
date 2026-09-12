from typing import override

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from user_app.context import require_current_user

from .models import Wallet
from .serializers import WalletSerializer


class WalletViewSet(ModelViewSet):
    """
    CRUD for wallets.

    - Regular users can only see and update their own wallet.
    - Staff users can see and manage all wallets.
    - Wallets are auto-created on user signup; direct POST is disabled.
    """

    serializer_class = WalletSerializer
    http_method_names = ["get", "patch", "put", "delete", "head", "options"]

    @override
    def get_queryset(self):
        user = require_current_user()
        # if user.is_staff:
        #     return Wallet.objects.select_related("user").all()
        return Wallet.objects.filter(user=user)
