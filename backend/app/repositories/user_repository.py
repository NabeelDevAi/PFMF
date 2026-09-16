from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.user import User


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return self.db.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        # CITEXT on the column already makes this comparison case-insensitive.
        return self.db.scalar(select(User).where(User.email == email))

    def create(self, *, email: str, password_hash: str) -> User:
        user = User(email=email, password_hash=password_hash)
        self.db.add(user)
        self.db.flush()  # populate user.id without committing the transaction
        return user

    def update_password(self, user: User, password_hash: str) -> None:
        user.password_hash = password_hash
        self.db.flush()

    def delete(self, user: User) -> None:
        """Cascades to everything the user owns -- user_settings,
        categories, scenarios (and transitively their transactions and
        overlays), refresh_tokens -- via each table's own ON DELETE
        CASCADE. Nothing else needs deleting."""
        self.db.delete(user)
        self.db.flush()
