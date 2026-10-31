from datetime import datetime

from sqlalchemy.orm import Session

from models.reminder import Reminders
from schemas.reminder import ReminderCreate, ReminderUpdate


class ReminderRepository:

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, reminder_id: int) -> Reminders | None:
        return self.db.query(Reminders).filter(Reminders.id == reminder_id).first()

    def get_all(self) -> list[Reminders]:
        return self.db.query(Reminders).all()

    def get_by_user_id(
        self, user_id: int, skip: int = 0, limit: int = 100
    ) -> list[Reminders]:
        return (
            self.db.query(Reminders)
            .filter(Reminders.user_id == user_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def create(self, reminder_data: ReminderCreate, user_id: int) -> Reminders:
        now = datetime.now()
        db_reminder = Reminders(
            title=reminder_data.title,
            description=reminder_data.description,
            due_date=reminder_data.due_date,
            is_completed=False,
            created_at=now,
            updated_at=now,
            user_id=user_id,
        )
        self.db.add(db_reminder)
        self.db.commit()
        self.db.refresh(db_reminder)
        return db_reminder

    def update(
        self, reminder_id: int, reminder_data: ReminderUpdate
    ) -> Reminders | None:
        db_reminder = self.get_by_id(reminder_id)
        if db_reminder:
            db_reminder.title = reminder_data.title
            db_reminder.description = reminder_data.description
            db_reminder.due_date = reminder_data.due_date
            db_reminder.is_completed = reminder_data.is_completed
            db_reminder.updated_at = datetime.now()
            self.db.commit()
            self.db.refresh(db_reminder)
            return db_reminder
        return None

    def delete(self, reminder_id: int) -> bool:
        db_reminder = self.get_by_id(reminder_id)
        if db_reminder:
            self.db.delete(db_reminder)
            self.db.commit()
            return True
        return False
