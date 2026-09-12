from rest_framework.request import Request
from rest_framework_simplejwt.authentication import JWTAuthentication

from user_app.context import set_current_user


class ContextAwareJWTAuthentication(JWTAuthentication):
    """
    JWT authentication that also writes the validated user into the
    per-request ContextVar immediately after token validation.

    This guarantees that get_current_user() / require_current_user()
    always return the correct user for the active request, regardless of
    where they are called (views, serializers, services, signals …) and
    regardless of how many concurrent requests are being handled.

    The ContextVar provides per-thread (WSGI) and per-asyncio-Task (ASGI)
    isolation, so requests can never bleed into one another.
    The CurrentUserMiddleware resets the ContextVar to None at the very
    start of each request, so an unauthenticated request can never
    accidentally inherit a user from a previous request on the same thread.
    """

    def authenticate(self, request: Request):
        result = super().authenticate(request)
        if result is not None:
            user, _ = result
            set_current_user(user)
        return result
