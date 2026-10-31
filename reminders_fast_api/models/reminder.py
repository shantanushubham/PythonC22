from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import mapped_column, relationship

from core.database import Base


class Reminders(Base):
    __tablename__ = "reminders"
    id = mapped_column(Integer, primary_key=True)
    title = mapped_column(String, nullable=False)
    description = mapped_column(String, nullable=False)
    due_date = mapped_column(DateTime, nullable=False)
    is_completed = mapped_column(Boolean, nullable=False)
    created_at = mapped_column(DateTime, nullable=False)
    updated_at = mapped_column(DateTime, nullable=False)

    user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False)

    # Relationship to User
    owner = relationship("User", back_populates="reminders")
