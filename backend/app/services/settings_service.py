from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.db.models.user_settings import UserSettings
from app.repositories.user_settings_repository import UserSettingsRepository


class SettingsService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = UserSettingsRepository(db)

    def get(self, user_id: uuid.UUID) -> UserSettings:
        settings = self.repo.get_by_user_id(user_id)
        if settings is None:
            # Every user gets a settings row at registration -- reaching
            # here means data is missing, not that the caller did anything
            # wrong, but resource.not_found is still the right client signal.
            raise APIError("resource.not_found")
        return settings

    def patch(
        self,
        user_id: uuid.UUID,
        *,
        display_name: str | None = None,
        currency_code: str | None = None,
        locale: str | None = None,
        current_balance_minor: int | None = None,
        balance_as_of: date | None = None,
    ) -> UserSettings:
        settings = self.get(user_id)
        if display_name is not None:
            settings.display_name = display_name
        if currency_code is not None:
            settings.currency_code = currency_code
        if locale is not None:
            settings.locale = locale
        if current_balance_minor is not None:
            settings.current_balance_minor = current_balance_minor
        if balance_as_of is not None:
            settings.balance_as_of = balance_as_of
        self.repo.save(settings)
        return settings
