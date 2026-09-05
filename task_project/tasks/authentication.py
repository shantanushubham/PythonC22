from typing import override
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request

from tasks.models import User
from tasks.utils import JwtUtil


class JwtAuthentication(BaseAuthentication):

    @override
    def authenticate(self, request: Request) -> tuple[User, str] | None:
        auth_header = request.headers.get("Authorization")

        if not auth_header:
            return None

        try:
            scheme, token = auth_header.split(" ", 1)
        except ValueError:
            raise AuthenticationFailed("Invalid Auth Header")

        if scheme.lower() != "bearer":
            raise AuthenticationFailed("Auth Header must be bearer.")

        payload = JwtUtil.verify_token(token)

        try:
            user_id = payload["user_id"]
        except KeyError:
            raise AuthenticationFailed("Invalid token Payload")

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise AuthenticationFailed(
                "User associated with this token does not exist."
            )

        return user, token
