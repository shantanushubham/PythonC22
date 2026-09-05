from typing import Any
import bcrypt
from datetime import datetime, timedelta, timezone
import jwt
from rest_framework.exceptions import AuthenticationFailed
from tasks.models import User


UTF_8 = "utf-8"
SECRET_KEY = "e0f2dddefac89066f3008b46071cd4c2032005b285b10158e93bd67c6981b054"
ALGORITHM = "HS256"


class BCryptUtil:

    @staticmethod
    def hash_password(plain_password: str) -> str:
        hash: bytes = bcrypt.hashpw(plain_password.encode(UTF_8), bcrypt.gensalt())
        return hash.decode(UTF_8)

    @staticmethod
    def validate_password(hashed_password: str, plain_password: str) -> bool:
        hashed_password_bytes: bytes = hashed_password.encode(UTF_8)
        plain_password_bytes: bytes = plain_password.encode(UTF_8)
        return bcrypt.checkpw(plain_password_bytes, hashed_password_bytes)


class JwtUtil:

    @staticmethod
    def create_access_token(user_id: int, role: User.Role) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "user_id": user_id,
            "role": role,
            "exp": now + timedelta(minutes=30),
            "iat": now,  # creation_time
        }

        return jwt.encode(payload, SECRET_KEY, ALGORITHM)

    @staticmethod
    def verify_token(access_token: str) -> dict[str, Any]:
        try:
            payload = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])
        except jwt.ExpiredSignatureError:
            raise AuthenticationFailed("Token has expired!")
        except jwt.InvalidTokenError:
            raise AuthenticationFailed("Invalid Token")

        return payload
