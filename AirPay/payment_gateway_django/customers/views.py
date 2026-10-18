from django.core.exceptions import ObjectDoesNotExist
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
from customers.models import APIKey
from customers.serialisers import (
    APIKeySerializer,
    CreateAPIKeySerializer,
    CreatedAPIKeySerializer,
    CustomerSerializer,
    LoginRequestSerializer,
    LoginSerializer,
    RefreshTokenSerializer,
    RegisterSerializer,
    TokenPairSerializer,
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
