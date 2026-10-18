from datetime import timedelta

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from customers.models import APIKey, Customer, normalize_email

EMAIL_TAKEN = "A customer with this email already exists."


class CustomerSerializer(serializers.ModelSerializer):
    """A customer as the API shows them. There is never a password in it."""

    class Meta:
        model = Customer
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "company_name",
            "company_address",
            "date_joined",
        ]
        # Only the four profile fields can be changed. The email is the login name, and
        # changing a login name needs its own verification step.
        read_only_fields = ["id", "email", "date_joined"]


class RegisterSerializer(serializers.ModelSerializer):
    """Sign up. Only the fields listed here are read, so a caller cannot send
    `is_staff` or `is_superuser` and make themselves an administrator."""

    # At most 150 characters, because the email is also stored as the username.
    email = serializers.EmailField(max_length=150)
    password = serializers.CharField(
        write_only=True,
        max_length=128,
        trim_whitespace=False,
        style={"input_type": "password"},
    )

    class Meta:
        model = Customer
        fields = [
            "email",
            "password",
            "first_name",
            "last_name",
            "company_name",
            "company_address",
        ]

    def validate_email(self, value: str) -> str:
        email = normalize_email(value)
        if Customer.objects.filter(Q(email=email) | Q(username=email)).exists():
            raise serializers.ValidationError(EMAIL_TAKEN)
        return email

    def validate_password(self, value: str) -> str:
        # Checked here, not in validate(), so a weak password is reported together with
        # any other mistakes. The other fields are read from the raw input because they
        # are not validated yet. They let Django reject a password that is too similar
        # to the customer's own email or name.
        raw = self.initial_data
        candidate = Customer(
            email=str(raw.get("email", "")),
            first_name=str(raw.get("first_name", "")),
            last_name=str(raw.get("last_name", "")),
        )
        try:
            validate_password(value, user=candidate)
        except DjangoValidationError as error:
            raise serializers.ValidationError(list(error.messages)) from error
        return value

    def create(self, validated_data):
        try:
            # The email is the login name, so it is also the username.
            return Customer.objects.create_user(username=validated_data["email"], **validated_data)
        except IntegrityError as error:
            # Two sign ups with the same email at the same moment. The database decides.
            raise serializers.ValidationError({"email": [EMAIL_TAKEN]}) from error


# --- Tokens ---------------------------------------------------------------------------------


class LoginSerializer(TokenObtainPairSerializer):
    """Log in with an email and password.

    The email is looked up as the username, which is where sign up stores it. It is
    lower-cased first, so `Jane@Example.com` and `jane@example.com` are the same login.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        del self.fields[self.username_field]
        self.fields["email"] = serializers.CharField(write_only=True)

    def validate(self, attrs):
        credentials = {
            self.username_field: normalize_email(attrs["email"]),
            "password": attrs["password"],
        }
        return super().validate(credentials)


# These describe the requests and responses in the API docs.


class LoginRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(style={"input_type": "password"})


class TokenPairSerializer(serializers.Serializer):
    access = serializers.CharField(help_text="Short lived. Send it as `Authorization: Bearer <access>`.")
    refresh = serializers.CharField(help_text="Long lived. Exchange it for a new pair at `/auth/refresh`.")


class RefreshTokenSerializer(serializers.Serializer):
    refresh = serializers.CharField()


# --- API keys ---------------------------------------------------------------------------


class APIKeySerializer(serializers.ModelSerializer):
    """A key as the API lists it. The secret is never in this shape."""

    status = serializers.CharField(read_only=True)

    class Meta:
        model = APIKey
        fields = [
            "id",
            "name",
            "prefix",
            "last_four",
            "status",
            "expires_at",
            "revoked_at",
            "last_used_at",
            "created_at",
        ]
        read_only_fields = fields


class CreatedAPIKeySerializer(APIKeySerializer):
    """Returned only from POST. `key` is the secret, shown this once."""

    key = serializers.CharField(
        read_only=True,
        help_text="The secret. Shown this once. Send it as `X-API-Key` on payment requests.",
    )

    class Meta(APIKeySerializer.Meta):
        fields = [*APIKeySerializer.Meta.fields, "key"]


class CreateAPIKeySerializer(serializers.Serializer):
    name = serializers.CharField(max_length=80, required=False, allow_blank=True, default="")
    expires_at = serializers.DateTimeField(
        help_text="When this key stops working. Must be in the future, at most 365 days from now."
    )

    def validate_expires_at(self, value):
        now = timezone.now()
        if value <= now:
            raise serializers.ValidationError("expires_at must be in the future.")
        latest = now + timedelta(days=settings.API_KEY_MAX_LIFETIME_DAYS)
        if value > latest:
            raise serializers.ValidationError(
                f"expires_at cannot be more than {settings.API_KEY_MAX_LIFETIME_DAYS} days from now."
            )
        return value

