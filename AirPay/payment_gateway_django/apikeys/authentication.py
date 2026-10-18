from datetime import timedelta

from django.db.models import Q
from django.utils import timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from apikeys.keys import digests_match, hash_key, parse_prefix
from apikeys.models import ApiKey

HEADER = "X-API-Key"

# last_used_at is written at most once a minute per key, so a busy key does not cause a
# database write on every request.
LAST_USED_RESOLUTION = timedelta(minutes=1)


class ApiKeyAuthentication(BaseAuthentication):
    """Authenticates a request by the `X-API-Key` header.

    On success `request.user` is the customer who owns the key and `request.auth` is the
    ApiKey. A key is refused when it is unknown, revoked, expired, or its customer has
    been deactivated.

    The key is only accepted in the header, never in the URL, so it does not end up in
    logs, browser history or referrer headers.
    """

    def authenticate(self, request):
        raw = request.headers.get(HEADER)
        if raw is None:
            return None  # no key sent. The permission check answers with 401.
        raw = raw.strip()

        # The hash is always computed and always compared, found or not, so the time a
        # request takes does not say whether a key exists.
        presented = hash_key(raw)
        prefix = parse_prefix(raw)
        api_key = (
            ApiKey.objects.select_related("customer").filter(prefix=prefix).first() if prefix else None
        )
        if not digests_match(api_key.key_hash if api_key else None, presented):
            raise AuthenticationFailed("Invalid API key.")

        # The caller proved they hold the real key, so it is safe to say why it is refused.
        now = timezone.now()
        if api_key.revoked_at is not None:
            raise AuthenticationFailed("This API key has been revoked.")
        if api_key.expires_at <= now:
            raise AuthenticationFailed("This API key has expired.")
        if not api_key.customer.is_active:
            raise AuthenticationFailed("Invalid API key.")

        self._record_use(api_key, now)
        return api_key.customer, api_key

    def authenticate_header(self, request):
        # Makes DRF answer 401, with this header, instead of 403.
        return 'ApiKey realm="api"'

    @staticmethod
    def _record_use(api_key: ApiKey, now) -> None:
        ApiKey.objects.filter(pk=api_key.pk).filter(
            Q(last_used_at__isnull=True) | Q(last_used_at__lt=now - LAST_USED_RESOLUTION)
        ).update(last_used_at=now)
