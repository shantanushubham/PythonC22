import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import IntegrityError, models, transaction
from django.utils import timezone

from customers.crypto import generate


def normalize_email(email: str) -> str:
    """Emails are compared case-insensitively, so they are stored in lower case."""
    return (email or "").strip().lower()


class Customer(AbstractUser):
    """A company that uses AirPay.

    Built on AbstractUser with Django's own manager, so it keeps password hashing,
    permissions, groups, `is_active`, `last_login` and admin support.

    `username` is Django's login name. For customers who sign up through the API it
    is their email address, so the email is what they log in with.
    The primary key is a UUID, so customer ids cannot be guessed or counted.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    email = models.EmailField("email address", unique=True)
    first_name = models.CharField("first name", max_length=150)
    last_name = models.CharField("last name", max_length=150)
    company_name = models.CharField("company name", max_length=150)
    company_address = models.CharField("company address", max_length=500)

    # Asked for by `createsuperuser`, together with the username and password.
    REQUIRED_FIELDS = ["email", "first_name", "last_name", "company_name", "company_address"]

    class Meta:
        ordering = ["email"]

    def save(self, *args, **kwargs):
        self.email = normalize_email(self.email)
        if not self.username:
            self.username = self.email
        super().save(*args, **kwargs)

    def __str__(self):
        return self.email


class APIKey(models.Model):
    """A key the customer uses to call the payment API.

    The secret itself is shown once, at creation, and then only its HMAC is kept.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="api_keys")
    name = models.CharField(max_length=80, blank=True, default="")
    # Public lookup, for example apk_a1b2c3d4e5f60789. Not a secret.
    prefix = models.CharField(max_length=20, unique=True)
    last_four = models.CharField(max_length=4)
    # HMAC-SHA256 of the full key, 64 hex characters.
    secret_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["customer", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.prefix}…{self.last_four}"

    @property
    def status(self) -> str:
        if self.revoked_at is not None:
            return "revoked"
        if timezone.now() >= self.expires_at:
            return "expired"
        return "active"

    def is_usable(self, at=None) -> bool:
        at = at or timezone.now()
        return (
            self.revoked_at is None
            and at < self.expires_at
            and self.customer.is_active
        )

    def revoke(self):
        if self.revoked_at is None:
            self.revoked_at = timezone.now()
            self.save(update_fields=["revoked_at"])

    def mark_used(self):
        APIKey.objects.filter(pk=self.pk).update(last_used_at=timezone.now())

    @classmethod
    def issue(cls, customer: Customer, *, name: str, expires_at) -> tuple["APIKey", str]:
        """Create a key and return ``(row, raw_secret)``. The raw secret is not stored."""
        last_error: IntegrityError | None = None
        for _ in range(5):
            material = generate()
            try:
                with transaction.atomic():
                    key = cls.objects.create(
                        customer=customer,
                        name=name,
                        prefix=material.prefix,
                        last_four=material.last_four,
                        secret_hash=material.secret_hash,
                        expires_at=expires_at,
                    )
                return key, material.raw
            except IntegrityError as error:
                last_error = error
        raise RuntimeError("Could not allocate a unique API key") from last_error

    @classmethod
    def active_count(cls, customer: Customer) -> int:
        return cls.objects.filter(
            customer=customer, revoked_at__isnull=True, expires_at__gt=timezone.now()
        ).count()

    @classmethod
    def at_limit(cls, customer: Customer) -> bool:
        return cls.active_count(customer) >= settings.API_KEY_MAX_PER_CUSTOMER
