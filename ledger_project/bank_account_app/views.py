from typing import override

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from user_app.context import require_current_user

from .models import BankAccount
from .serializers import BankAccountSerializer


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
        return BankAccount.objects.filter(user=user)

    @override
    def perform_create(self, serializer) -> None:
        """Attach the logged-in user automatically on creation."""
        user = require_current_user()
        serializer.save(user=user)

    @override
    def destroy(self, request: Request, *args, **kwargs) -> Response:
        instance = self.get_object()
        setattr(instance, "is_active", False)
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
