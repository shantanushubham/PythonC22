import logging
from typing import override

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from user_app.context import require_current_user

from .models import BankAccount
from .serializers import BankAccountSerializer

logger = logging.getLogger(__name__)


class BankAccountViewSet(ModelViewSet):
    """
    Full CRUD for bank accounts.

    Every action is scoped to the logged-in user:
      - list     GET    /api/bank-accounts/
      - create   POST   /api/bank-accounts/
      - retrieve GET    /api/bank-accounts/{id}/
      - update   PUT    /api/bank-accounts/{id}/
      - partial  PATCH  /api/bank-accounts/{id}/
      - destroy  DELETE /api/bank-accounts/{id}/
    """

    serializer_class = BankAccountSerializer

    @override
    def get_queryset(self):
        user = require_current_user()
        logger.info(
            "class=BankAccountViewSet op=get_queryset message=listing bank accounts user_id=%s",
            user.id,
        )
        return BankAccount.objects.filter(user=user)

    @override
    def perform_create(self, serializer) -> None:
        """Attach the logged-in user automatically on creation."""
        user = require_current_user()
        logger.info(
            "class=BankAccountViewSet op=perform_create message=creating bank account user_id=%s",
            user.id,
        )
        serializer.save(user=user)

    @override
    def destroy(self, request: Request, *args, **kwargs) -> Response:
        instance = self.get_object()
        setattr(instance, "is_active", False)
        instance.save()
        logger.info(
            "class=BankAccountViewSet op=destroy message=deactivated bank account bank_account_id=%s",
            instance.id,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
