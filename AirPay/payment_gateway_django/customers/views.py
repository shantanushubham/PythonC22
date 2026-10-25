from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from core.serialisers import ErrorSerializer, ValidationErrorSerializer

from customers.models import APIKey, BankAccount
from customers.serialisers import (
    APIKeySerializer,
    AddBankAccountSerializer,
    BankAccountSerializer,
    CreateAPIKeySerializer,
    CreatedAPIKeySerializer,
    CustomerSerializer,
    LoginRequestSerializer,
    LoginSerializer,
    RefreshTokenSerializer,
    RegisterSerializer,
    TokenPairSerializer,
    UpdateBankAccountSerializer,
)
from customers.throttles import LoginRateThrottle

BAD_REQUEST = OpenApiResponse(ValidationErrorSerializer, description="A field is missing or invalid.")
UNAUTHORIZED = OpenApiResponse(ErrorSerializer, description="The token or the credentials are not valid.")
TOO_MANY = OpenApiResponse(ErrorSerializer, description="Too many requests. See the `Retry-After` header.")


class RegisterView(APIView):
    """Sign up as a customer."""

    authentication_classes: list = []
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="registerCustomer",
        tags=["Customers"],
        summary="Sign up",
        request=RegisterSerializer,
        responses={201: CustomerSerializer, 400: BAD_REQUEST, 429: TOO_MANY},
    )
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        customer = serializer.save()
        return Response(CustomerSerializer(customer).data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    get=extend_schema(
        operation_id="getCurrentCustomer",
        tags=["Customers"],
        summary="Get your own account",
        responses={200: CustomerSerializer, 401: UNAUTHORIZED},
    ),
    patch=extend_schema(
        operation_id="updateCurrentCustomer",
        tags=["Customers"],
        summary="Update your name and company details",
        description="Only `first_name`, `last_name`, `company_name` and `company_address` can change. "
        "Other fields in the request are ignored.",
        responses={200: CustomerSerializer, 400: BAD_REQUEST, 401: UNAUTHORIZED},
    ),
)
class CurrentCustomerView(generics.RetrieveUpdateAPIView):
    """The logged in customer. Needs an access token."""

    serializer_class = CustomerSerializer
    # No PUT: a full replace makes no sense when the email and id cannot be replaced.
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        return self.request.user


@extend_schema_view(
    post=extend_schema(
        operation_id="login",
        tags=["Auth"],
        summary="Log in",
        description="Exchange an email and password for an access token and a refresh token. "
        "A wrong password and an unknown email give the same answer.",
        request=LoginRequestSerializer,
        responses={
            200: TokenPairSerializer,
            400: BAD_REQUEST,
            401: UNAUTHORIZED,
            429: TOO_MANY,
        },
    )
)
class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer
    throttle_classes = [LoginRateThrottle]


@extend_schema_view(
    post=extend_schema(
        operation_id="refreshToken",
        tags=["Auth"],
        summary="Get a new access token",
        description="Send a refresh token. The response has a new access token and a new "
        "refresh token. The refresh token you sent stops working, so keep the new one.",
        request=RefreshTokenSerializer,
        responses={200: TokenPairSerializer, 400: BAD_REQUEST, 401: UNAUTHORIZED, 429: TOO_MANY},
    )
)
class RefreshView(TokenRefreshView):
    def post(self, request, *args, **kwargs):
        try:
            return super().post(request, *args, **kwargs)
        except ObjectDoesNotExist as error:
            # The customer was deleted after the token was issued. simplejwt does not
            # handle this case and would answer 500.
            raise InvalidToken("Token is invalid") from error


class LogoutView(APIView):
    """Revoke a refresh token."""

    authentication_classes: list = []
    permission_classes = [AllowAny]

    def get_authenticate_header(self, request):
        # Without this, DRF turns the 401 for a bad token into a 403.
        return 'Bearer realm="api"'

    @extend_schema(
        operation_id="logout",
        tags=["Auth"],
        summary="Log out",
        description="Revokes the refresh token, so it can no longer be used to get new tokens. "
        "An access token that was already issued keeps working until it expires "
        "(15 minutes by default). Discard it on the client.",
        request=RefreshTokenSerializer,
        responses={204: OpenApiResponse(description="The refresh token was revoked."), 400: BAD_REQUEST, 401: UNAUTHORIZED},
    )
    def post(self, request):
        serializer = RefreshTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            RefreshToken(serializer.validated_data["refresh"]).blacklist()
        except TokenError as error:
            raise InvalidToken(error.args[0]) from error
        return Response(status=status.HTTP_204_NO_CONTENT)


# --- API keys. JWT only: a payment API key cannot manage other keys. -----------------------

FORBIDDEN = OpenApiResponse(ErrorSerializer, description="Not allowed.")
NOT_FOUND = OpenApiResponse(ErrorSerializer, description="No API key with that id.")


class APIKeyListCreateView(APIView):
    """List this customer's keys, or create a new one. Needs a JWT access token."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="listAPIKeys",
        tags=["API keys"],
        summary="List your API keys",
        description="The secret is never included. Use `prefix` and `last_four` to recognise a key.",
        responses={200: APIKeySerializer(many=True), 401: UNAUTHORIZED},
    )
    def get(self, request):
        keys = APIKey.objects.filter(customer=request.user)
        return Response(APIKeySerializer(keys, many=True).data)

    @extend_schema(
        operation_id="createAPIKey",
        tags=["API keys"],
        summary="Create an API key",
        description="The full key is in `key` and is shown this once. Store it. "
        "Payment endpoints take it as `X-API-Key`.",
        request=CreateAPIKeySerializer,
        responses={201: CreatedAPIKeySerializer, 400: BAD_REQUEST, 401: UNAUTHORIZED},
    )
    def post(self, request):
        serializer = CreateAPIKeySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if APIKey.at_limit(request.user):
            raise ValidationError(
                {"non_field_errors": ["You already have the maximum number of active API keys."]}
            )
        key, raw = APIKey.issue(
            request.user,
            name=serializer.validated_data["name"],
            expires_at=serializer.validated_data["expires_at"],
        )
        body = dict(APIKeySerializer(key).data)
        body["key"] = raw
        return Response(body, status=status.HTTP_201_CREATED)


class APIKeyDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _key(self, request, key_id):
        return get_object_or_404(APIKey, pk=key_id, customer=request.user)

    @extend_schema(
        operation_id="getAPIKey",
        tags=["API keys"],
        summary="Get one of your API keys",
        responses={200: APIKeySerializer, 401: UNAUTHORIZED, 404: NOT_FOUND},
    )
    def get(self, request, key_id):
        return Response(APIKeySerializer(self._key(request, key_id)).data)

    @extend_schema(
        operation_id="revokeAPIKey",
        tags=["API keys"],
        summary="Revoke an API key",
        description="The key stops working at once. Idempotent: revoking twice is still 204.",
        responses={204: OpenApiResponse(description="The key was revoked."), 401: UNAUTHORIZED, 404: NOT_FOUND},
    )
    def delete(self, request, key_id):
        self._key(request, key_id).revoke()
        return Response(status=status.HTTP_204_NO_CONTENT)


# --- Bank accounts. JWT only. -------------------------------------------------------------

ACCOUNT_NOT_FOUND = OpenApiResponse(ErrorSerializer, description="No bank account with that id.")


class BankAccountListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="listBankAccounts",
        tags=["Bank accounts"],
        summary="List your bank accounts",
        description="The full account number is never included. Use `account_number_last_four` and `ifsc`.",
        responses={200: BankAccountSerializer(many=True), 401: UNAUTHORIZED},
    )
    def get(self, request):
        accounts = BankAccount.objects.filter(customer=request.user, revoked_at__isnull=True)
        return Response(BankAccountSerializer(accounts, many=True).data)

    @extend_schema(
        operation_id="addBankAccount",
        tags=["Bank accounts"],
        summary="Add a bank account",
        request=AddBankAccountSerializer,
        responses={201: BankAccountSerializer, 400: BAD_REQUEST, 401: UNAUTHORIZED},
    )
    def post(self, request):
        serializer = AddBankAccountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if BankAccount.at_limit(request.user):
            raise ValidationError(
                {"non_field_errors": ["You already have the maximum number of bank accounts."]}
            )
        try:
            account = BankAccount.add(request.user, **serializer.validated_data)
        except IntegrityError:
            raise ValidationError(
                {"account_number": ["This bank account is already registered."]}
            ) from None
        return Response(BankAccountSerializer(account).data, status=status.HTTP_201_CREATED)


class BankAccountDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _account(self, request, account_id):
        return get_object_or_404(
            BankAccount, pk=account_id, customer=request.user, revoked_at__isnull=True
        )

    @extend_schema(
        operation_id="getBankAccount",
        tags=["Bank accounts"],
        summary="Get one of your bank accounts",
        responses={200: BankAccountSerializer, 401: UNAUTHORIZED, 404: ACCOUNT_NOT_FOUND},
    )
    def get(self, request, account_id):
        return Response(BankAccountSerializer(self._account(request, account_id)).data)

    @extend_schema(
        operation_id="updateBankAccount",
        tags=["Bank accounts"],
        summary="Update the label or default flag",
        description="The account number and IFSC cannot change. Add a new account instead.",
        request=UpdateBankAccountSerializer,
        responses={200: BankAccountSerializer, 400: BAD_REQUEST, 401: UNAUTHORIZED, 404: ACCOUNT_NOT_FOUND},
    )
    def patch(self, request, account_id):
        account = self._account(request, account_id)
        serializer = UpdateBankAccountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if not data:
            return Response(BankAccountSerializer(account).data)
        with transaction.atomic():
            if data.get("is_default") is True:
                BankAccount.objects.filter(customer=request.user, is_default=True).update(is_default=False)
                account.is_default = True
            elif data.get("is_default") is False and account.is_default:
                raise ValidationError(
                    {"is_default": ["Set another account as default instead of unsetting this one."]}
                )
            if "account_holder_name" in data:
                account.account_holder_name = data["account_holder_name"]
            if "bank_name" in data:
                account.bank_name = data["bank_name"]
            account.save()
        return Response(BankAccountSerializer(account).data)

    @extend_schema(
        operation_id="removeBankAccount",
        tags=["Bank accounts"],
        summary="Remove a bank account",
        description="The account can no longer be used for payouts. Existing payouts keep a snapshot.",
        responses={204: OpenApiResponse(description="Removed."), 401: UNAUTHORIZED, 404: ACCOUNT_NOT_FOUND},
    )
    def delete(self, request, account_id):
        account = self._account(request, account_id)
        account.revoke()
        replacement = (
            BankAccount.objects.filter(customer=request.user, revoked_at__isnull=True)
            .order_by("-created_at")
            .first()
        )
        if replacement and not BankAccount.objects.filter(customer=request.user, is_default=True).exists():
            replacement.is_default = True
            replacement.save(update_fields=["is_default"])
        return Response(status=status.HTTP_204_NO_CONTENT)
