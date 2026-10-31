from datetime import datetime

from sqlalchemy.orm import Session

from models.user import User
from schemas.user import UserCreate, UserUpdate
from utils.security import hash_password


class UserRepository:

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, user_id: int) -> User | None:
        # User.objects.get(id=user_id)
        return self.db.query(User).filter(User.id == user_id).first()

    def get_by_email(self, email: str) -> User | None:
        return self.db.query(User).filter(User.email == email).first()

    def get_all(self, skip: int = 0, limit: int = 100) -> list[User]:
        return self.db.query(User).offset(skip).limit(limit).all()

    def create(self, user_data: UserCreate, hashed_password: str) -> User:
        now = datetime.now()
        db_user = User(
            email=user_data.email,
            hashed_password=hashed_password,
            created_at=now,
            updated_at=now,
        )
        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)
        return db_user

    def update(self, user_id: int, user_data: UserUpdate) -> User | None:
        db_user = self.get_by_id(user_id)
        if db_user:
            db_user.email = user_data.email
            db_user.hashed_password = hash_password(user_data.password)
            db_user.updated_at = datetime.now()
            self.db.commit()
            self.db.refresh(db_user)
            return db_user
        return None

    def delete(self, user_id: int) -> bool:
        db_user = self.get_by_id(user_id)
        if db_user:
            self.db.delete(db_user)
            self.db.commit()
            return True
        return False
