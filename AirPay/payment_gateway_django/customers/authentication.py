"""Authenticate payment requests with an API key.

Dashboard calls use JWT (``Authorization: Bearer …``). Payment calls use an API
key, sent as ``X-API-Key`` or ``Authorization: Api-Key …``. The two are never
accepted on the same view, so a dashboard token cannot be used as a payment key
and a payment key cannot be used as a dashboard token.
"""

from drf_spectacular.extensions import OpenApiAuthenticationExtension
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from customers.crypto import prefix_of, verify
from customers.models import APIKey

HEADER = "X-API-Key"
SCHEME = "Api-Key"
INVALID = "Invalid API key"


class APIKeyAuthentication(BaseAuthentication):
    def authenticate(self, request):
        raw = _extract(request)
        if raw is None:
            return None

        key = _lookup(raw)
        if key is None or not verify(raw, key.secret_hash):
            raise AuthenticationFailed(INVALID)
        if not key.customer.is_active:
            raise AuthenticationFailed(INVALID)
        if key.revoked_at is not None:
            raise AuthenticationFailed("API key has been revoked")
        if not key.is_usable():
            raise AuthenticationFailed("API key has expired")

        key.mark_used()
        request.api_key = key
        return (key.customer, key)

    def authenticate_header(self, request):
        # Makes DRF answer 401, not 403, when the header is missing or wrong.
        return f'{SCHEME} realm="api"'


def _extract(request) -> str | None:
    named = request.headers.get(HEADER)
    if named:
        return named.strip() or None

    header = get_authorization_header(request).decode("utf-8")
    if not header:
        return None
    parts = header.split()
    if parts[0] != SCHEME:
        # A Bearer JWT must not be treated as an API key.
        return None
    if len(parts) != 2:
        raise AuthenticationFailed("Authorization header must contain two space-delimited values")
    return parts[1]


def _lookup(raw: str) -> APIKey | None:
    prefix = prefix_of(raw)
    if prefix is None:
        # Still run HMAC against a dummy so a malformed key is not faster to reject.
        verify(raw, None)
        return None
    return APIKey.objects.select_related("customer").filter(prefix=prefix).first()


class APIKeyScheme(OpenApiAuthenticationExtension):
    target_class = "customers.authentication.APIKeyAuthentication"
    name = "apiKeyAuth"

    def get_security_definition(self, auto_schema):
        return {
            "type": "apiKey",
            "in": "header",
            "name": HEADER,
            "description": "An AirPay API key. This is how payment endpoints are called. "
            "Dashboard endpoints take a JWT instead.",
        }
