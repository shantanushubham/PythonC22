from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ReminderCreate(BaseModel):
    title: str
    description: str
    due_date: datetime


class ReminderUpdate(BaseModel):
    title: str
    description: str
    due_date: datetime
    is_completed: bool


class ReminderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    due_date: datetime
    is_completed: bool
    created_at: datetime
    updated_at: datetime
    user_id: int
