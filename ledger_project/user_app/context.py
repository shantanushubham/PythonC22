from contextvars import ContextVar, Token

from rest_framework.exceptions import AuthenticationFailed

# Import inside TYPE_CHECKING to avoid circular imports at runtime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from user_app.models import User

# Stores the authenticated User for the current request context.
# Each thread (WSGI) or asyncio Task (ASGI) gets its own isolated value,
# so concurrent requests never see each other's user.
_current_user: ContextVar["User | None"] = ContextVar(
    "current_user", default=None
)


def get_current_user() -> "User | None":
    return _current_user.get()


def require_current_user() -> "User":
    user = get_current_user()
    if user is None:
        raise AuthenticationFailed("Authentication credentials were not provided.")
    return user


def set_current_user(user: "User | None") -> "Token[User | None]":
    return _current_user.set(user)


def reset_current_user(token: "Token[User | None]") -> None:
    _current_user.reset(token)
