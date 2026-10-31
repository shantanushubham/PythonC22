from fastapi import APIRouter, Depends, status

from core.auth import get_current_user, require_self
from models.user import User
from schemas.user import (
    RefreshTokenRequest,
    Token,
    UserCreate,
    UserLogin,
    UserResponse,
    UserUpdate,
)
from services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])

UNAUTHORIZED = {401: {"description": "Missing, invalid, or expired token"}}
FORBIDDEN = {403: {"description": "Not allowed to access another user"}}
NOT_FOUND = {404: {"description": "User not found"}}
EMAIL_TAKEN = {400: {"description": "Email already registered"}}


@router.post(
    "/",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a user",
    responses=EMAIL_TAKEN,
)
def create_user(user_data: UserCreate, user_service: UserService = Depends()):
    return user_service.create_user(user_data)


@router.post(
    "/login",
    response_model=Token,
    summary="Log in",
    description="Returns an access token and a refresh token.",
    responses={401: {"description": "Incorrect email or password"}},
)
def login(credentials: UserLogin, user_service: UserService = Depends()):
    return user_service.login(credentials)


@router.post(
    "/refresh",
    response_model=Token,
    summary="Refresh tokens",
    description="Exchanges a refresh token for a new access token and refresh token. "
    "An access token is rejected.",
    responses=UNAUTHORIZED,
)
def refresh_token(body: RefreshTokenRequest, user_service: UserService = Depends()):
    return user_service.refresh(body.refresh_token)


@router.get("/", response_model=list[UserResponse], summary="List users")
def get_all_users(
    skip: int = 0, limit: int = 100, user_service: UserService = Depends()
):
    return user_service.get_all_users(skip, limit)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get the signed-in user",
    responses=UNAUTHORIZED,
)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Get a user",
    responses={**UNAUTHORIZED, **FORBIDDEN, **NOT_FOUND},
)
def get_user(
    user_id: int,
    user_service: UserService = Depends(),
    current_user: User = Depends(get_current_user),
):
    require_self(current_user, user_id)
    return user_service.get_user_by_id(user_id)


@router.put(
    "/{user_id}",
    response_model=UserResponse,
    summary="Update a user",
    responses={**UNAUTHORIZED, **FORBIDDEN, **NOT_FOUND, **EMAIL_TAKEN},
)
def update_user(
    user_id: int,
    user_data: UserUpdate,
    user_service: UserService = Depends(),
    current_user: User = Depends(get_current_user),
):
    require_self(current_user, user_id)
    return user_service.update_user(user_id, user_data)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a user",
    responses={**UNAUTHORIZED, **FORBIDDEN, **NOT_FOUND},
)
def delete_user(
    user_id: int,
    user_service: UserService = Depends(),
    current_user: User = Depends(get_current_user),
):
    require_self(current_user, user_id)
    user_service.delete_user(user_id)
