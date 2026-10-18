from rest_framework.throttling import SimpleRateThrottle

from apikeys.models import ApiKey


class ApiKeyRateThrottle(SimpleRateThrottle):
    """Limits requests per API key (API_KEY_RATE, 600 a minute by default).

    The limit is per key, not per address, so one busy integration cannot use up another
    customer's allowance, and a customer's keys do not share a limit.
    """

    scope = "api_key"

    def get_cache_key(self, request, view):
        if not isinstance(request.auth, ApiKey):
            return None
        return self.cache_format % {"scope": self.scope, "ident": str(request.auth.pk)}
