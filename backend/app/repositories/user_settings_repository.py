from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.db.models.user_settings import UserSettings


class UserSettingsRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_user_id(self, user_id: uuid.UUID) -> UserSettings | None:
        return self.db.get(UserSettings, user_id)

    def create_default(self, *, user_id: uuid.UUID, opening_balance_date: date) -> UserSettings:
        settings = UserSettings(user_id=user_id, opening_balance_date=opening_balance_date)
        self.db.add(settings)
        self.db.flush()
        return settings

    def save(self, settings: UserSettings) -> None:
        self.db.flush()
