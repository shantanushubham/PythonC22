from fastapi import APIRouter, Depends, status

from core.auth import get_current_user
from models.user import User
from schemas.reminder import ReminderCreate, ReminderResponse, ReminderUpdate
from services.reminder_service import ReminderService

router = APIRouter(prefix="/reminders", tags=["reminders"])

UNAUTHORIZED = {401: {"description": "Missing, invalid, or expired token"}}
NOT_FOUND = {404: {"description": "Reminder not found or owned by another user"}}


@router.post(
    "/",
    response_model=ReminderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a reminder",
    responses=UNAUTHORIZED,
)
def create_reminder(
    reminder_data: ReminderCreate,
    reminder_service: ReminderService = Depends(),
    current_user: User = Depends(get_current_user),
):
    return reminder_service.create_reminder(reminder_data, current_user.id)


@router.get(
    "/",
    response_model=list[ReminderResponse],
    summary="List my reminders",
    responses=UNAUTHORIZED,
)
def get_reminders(
    skip: int = 0,
    limit: int = 100,
    reminder_service: ReminderService = Depends(),
    current_user: User = Depends(get_current_user),
):
    return reminder_service.get_reminders(current_user.id, skip, limit)


@router.get(
    "/{reminder_id}",
    response_model=ReminderResponse,
    summary="Get a reminder",
    responses={**UNAUTHORIZED, **NOT_FOUND},
)
def get_reminder(
    reminder_id: int,
    reminder_service: ReminderService = Depends(),
    current_user: User = Depends(get_current_user),
):
    return reminder_service.get_reminder(reminder_id, current_user.id)


@router.put(
    "/{reminder_id}",
    response_model=ReminderResponse,
    summary="Update a reminder",
    responses={**UNAUTHORIZED, **NOT_FOUND},
)
def update_reminder(
    reminder_id: int,
    reminder_data: ReminderUpdate,
    reminder_service: ReminderService = Depends(),
    current_user: User = Depends(get_current_user),
):
    return reminder_service.update_reminder(reminder_id, reminder_data, current_user.id)


@router.delete(
    "/{reminder_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a reminder",
    responses={**UNAUTHORIZED, **NOT_FOUND},
)
def delete_reminder(
    reminder_id: int,
    reminder_service: ReminderService = Depends(),
    current_user: User = Depends(get_current_user),
):
    reminder_service.delete_reminder(reminder_id, current_user.id)
