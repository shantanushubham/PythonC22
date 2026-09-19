import logging
from typing import override

from django.db import transaction
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from user_app.context import require_current_user
from user_app.models import User
from user_app.serializers import LoginSerializer, UserSerializer, UserSignUpSerializer
from wallet_app.models import Wallet

logger = logging.getLogger(__name__)


class UserViewSet(ModelViewSet):

    queryset = User.objects.all()
    serializer_class = UserSignUpSerializer

    @override
    def get_serializer_class(self):
        if self.action in ("update", "partial_update"):
            return UserSerializer
        return UserSignUpSerializer

    @override
    def get_queryset(self):
        user = require_current_user()
        logger.info(
            "class=UserViewSet op=get_queryset message=listing users user_id=%s is_staff=%s",
            user.id, user.is_staff,
        )
        if user.is_staff:
            return User.objects.all()
        return User.objects.filter(pk=user.pk)

    @override
    def create(self, request: Request, *args, **kwargs) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            user = serializer.save()  # Success
            Wallet.objects.create(user=user)

        logger.info(
            "class=UserViewSet op=create message=user signed up user_id=%s", user.id
        )
        return Response(
            data={"id": user.id, "phone_number": user.phone_number},
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):

    def post(self, request: Request) -> Response:
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        logger.info(
            "class=LoginView op=post message=login successful phone_number=%s",
            request.data.get("phone_number"),
        )
        return Response(serializer.validated_data, status=status.HTTP_200_OK)
