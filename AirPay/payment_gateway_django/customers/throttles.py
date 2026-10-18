from rest_framework.throttling import AnonRateThrottle


class LoginRateThrottle(AnonRateThrottle):
    """Limits login attempts per IP address (API_LOGIN_RATE, 10 a minute by default).

    The limit is per address and not per account, so a stranger cannot lock a real
    customer out by guessing their email.
    """

    scope = "login"
