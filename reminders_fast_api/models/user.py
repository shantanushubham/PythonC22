from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import mapped_column, relationship

from core.database import Base


class User(Base):
    __tablename__ = "users"
    id = mapped_column(Integer, primary_key=True)
    email = mapped_column(String, unique=True, nullable=False)
    hashed_password = mapped_column(String, nullable=False)
    created_at = mapped_column(DateTime, nullable=False)
    updated_at = mapped_column(DateTime, nullable=False)

    # Relationship to Reminders
    reminders = relationship(
        "Reminders", back_populates="owner", cascade="all, delete-orphan"
    )
