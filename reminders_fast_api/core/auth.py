from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from core.database import get_db
from core.logging_config import get_logger
from models.user import User
from repositories.user_repository import UserRepository
from utils.security import decode_access_token

logger = get_logger("auth")

bearer_scheme = HTTPBearer(
    auto_error=False,
    description="Paste the access_token from POST /users/login (without the Bearer prefix).",
)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or credentials.scheme.lower() != "bearer":
        logger.warning("Auth rejected: missing bearer token")
        raise credentials_exception
    payload = decode_access_token(credentials.credentials)
    if payload is None or payload.get("sub") is None:
        logger.warning("Auth rejected: invalid or expired access token")
        raise credentials_exception
    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError):
        logger.warning("Auth rejected: malformed subject")
        raise credentials_exception
    user = UserRepository(db).get_by_id(user_id)
    if user is None:
        logger.warning("Auth rejected: user not found id=%s", user_id)
        raise credentials_exception
    return user


def require_self(current_user: User, user_id: int) -> None:
    if current_user.id != user_id:
        logger.warning(
            "Forbidden: user_id=%s tried to access user_id=%s", current_user.id, user_id
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not allowed to access this user",
        )
