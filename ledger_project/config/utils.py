import logging
from typing import Any
from datetime import datetime, timedelta, timezone
import jwt
from rest_framework.exceptions import AuthenticationFailed

logger = logging.getLogger(__name__)

UTF_8 = "utf-8"
SECRET_KEY = "e0f2dddefac89066f3008b46071cd4c2032005b285b10158e93bd67c6981b054"
ALGORITHM = "HS256"


class JwtUtil:

    @staticmethod
    def create_access_token(user_id: int, role: str) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "user_id": user_id,
            "role": role,
            "exp": now + timedelta(minutes=30),
            "iat": now,  # creation_time
        }

        logger.info(
            "class=JwtUtil op=create_access_token message=access token created "
            "user_id=%s role=%s",
            user_id, role,
        )
        return jwt.encode(payload, SECRET_KEY, ALGORITHM)

    @staticmethod
    def verify_token(access_token: str) -> dict[str, Any]:
        try:
            payload = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])
        except jwt.ExpiredSignatureError:
            logger.warning("class=JwtUtil op=verify_token message=token has expired")
            raise AuthenticationFailed("Token has expired!")
        except jwt.InvalidTokenError:
            logger.warning("class=JwtUtil op=verify_token message=invalid token")
            raise AuthenticationFailed("Invalid Token")

        return payload
