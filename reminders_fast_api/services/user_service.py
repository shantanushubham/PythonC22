from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.database import get_db
from core.logging_config import get_logger
from repositories.user_repository import UserRepository
from schemas.user import UserCreate, UserLogin, UserUpdate
from utils.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)

logger = get_logger("user_service")


class UserService:

    def __init__(self, session: Session = Depends(get_db)):
        self.user_repository = UserRepository(session)

    def create_user(self, user_data: UserCreate):
        existing_user = self.user_repository.get_by_email(user_data.email)
        if existing_user:
            logger.warning("Registration rejected: email already registered")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )
        hashed_password = hash_password(user_data.password)
        user = self.user_repository.create(user_data, hashed_password)
        logger.info("User created id=%s", user.id)
        return user

    def login(self, credentials: UserLogin) -> dict:
        user = self.user_repository.get_by_email(credentials.email)
        if not user or not verify_password(credentials.password, user.hashed_password):
            logger.warning("Login failed")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        logger.info("Login succeeded user_id=%s", user.id)
        return self._issue_tokens(user.id)

    def refresh(self, refresh_token: str) -> dict:
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        payload = decode_refresh_token(refresh_token)
        if payload is None or payload.get("sub") is None:
            logger.warning("Token refresh rejected: invalid refresh token")
            raise credentials_exception
        try:
            user_id = int(payload["sub"])
        except (TypeError, ValueError):
            logger.warning("Token refresh rejected: malformed subject")
            raise credentials_exception
        user = self.user_repository.get_by_id(user_id)
        if user is None:
            logger.warning("Token refresh rejected: user not found id=%s", user_id)
            raise credentials_exception
        logger.info("Token refreshed user_id=%s", user.id)
        return self._issue_tokens(user.id)

    def _issue_tokens(self, user_id: int) -> dict:
        subject = str(user_id)
        return {
            "access_token": create_access_token(subject),
            "refresh_token": create_refresh_token(subject),
            "token_type": "bearer",
        }

    def get_all_users(self, skip: int = 0, limit: int = 100):
        return self.user_repository.get_all(skip, limit)

    def get_user_by_id(self, user_id: int):
        user = self.user_repository.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )
        return user

    def update_user(self, user_id: int, user_data: UserUpdate):
        existing_user = self.user_repository.get_by_email(user_data.email)
        if existing_user and existing_user.id != user_id:
            logger.warning("Update rejected: email already registered user_id=%s", user_id)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )
        user = self.user_repository.update(user_id, user_data)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )
        logger.info("User updated id=%s", user_id)
        return user

    def delete_user(self, user_id: int):
        user = self.user_repository.delete(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )
        logger.info("User deleted id=%s", user_id)
        return user
