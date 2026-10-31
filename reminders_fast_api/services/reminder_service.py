from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.database import get_db
from core.logging_config import get_logger
from repositories.reminder_repository import ReminderRepository
from schemas.reminder import ReminderCreate, ReminderUpdate

logger = get_logger("reminder_service")


class ReminderService:

    def __init__(self, session: Session = Depends(get_db)):
        self.reminder_repository = ReminderRepository(session)

    def create_reminder(self, reminder_data: ReminderCreate, user_id: int):
        reminder = self.reminder_repository.create(reminder_data, user_id)
        logger.info("Reminder created id=%s user_id=%s", reminder.id, user_id)
        return reminder

    def get_reminders(self, user_id: int, skip: int = 0, limit: int = 100):
        return self.reminder_repository.get_by_user_id(user_id, skip, limit)

    def get_reminder(self, reminder_id: int, user_id: int):
        reminder = self.reminder_repository.get_by_id(reminder_id)
        if not reminder or reminder.user_id != user_id:
            logger.warning(
                "Reminder not found or not owned id=%s user_id=%s",
                reminder_id,
                user_id,
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found"
            )
        return reminder

    def update_reminder(
        self, reminder_id: int, reminder_data: ReminderUpdate, user_id: int
    ):
        self.get_reminder(reminder_id, user_id)
        reminder = self.reminder_repository.update(reminder_id, reminder_data)
        if not reminder:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found"
            )
        logger.info("Reminder updated id=%s user_id=%s", reminder_id, user_id)
        return reminder

    def delete_reminder(self, reminder_id: int, user_id: int):
        self.get_reminder(reminder_id, user_id)
        deleted = self.reminder_repository.delete(reminder_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found"
            )
        logger.info("Reminder deleted id=%s user_id=%s", reminder_id, user_id)
        return deleted
