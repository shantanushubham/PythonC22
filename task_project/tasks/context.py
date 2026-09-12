from contextvars import ContextVar, Token

from rest_framework.exceptions import AuthenticationFailed

from tasks.models import User

_current_user: ContextVar[User | None] = ContextVar("current_user", default=None)


def get_current_user() -> User | None:
    return _current_user.get()


def require_current_user() -> User:
    user = _current_user.get()
    if user is None:
        raise AuthenticationFailed("Authentication credentials were not provided.")
    return user


def set_current_user(user: User | None) -> Token[User | None]:
    return _current_user.set(user)


def reset_current_user(token: Token[User | None]) -> None:
    _current_user.reset(token)
