import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class ApiKey(models.Model):
    """One API key belonging to a customer.

    The key itself is not stored, only a hash of it (see apikeys/keys.py).
    A customer can have many keys, so each application or environment gets its own and
    one can be revoked without breaking the others.
    """

    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="api_keys"
    )
    name = models.CharField(max_length=100, help_text="A label, for example 'production server'.")
    prefix = models.CharField(max_length=12, unique=True, editable=False)
    key_hash = models.CharField(max_length=64, editable=False)

    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["customer", "-created_at"])]

    def __str__(self):
        return f"apk_{self.prefix}… ({self.name})"

    @property
    def status(self) -> str:
        if self.revoked_at is not None:
            return self.REVOKED
        if self.expires_at <= timezone.now():
            return self.EXPIRED
        return self.ACTIVE
