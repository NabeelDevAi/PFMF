from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.api.errors import APIError
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
        opening_balance_minor: int | None = None,
        opening_balance_date: date | None = None,
    ) -> UserSettings:
        settings = self.get(user_id)
        if display_name is not None:
            settings.display_name = display_name
        if currency_code is not None:
            settings.currency_code = currency_code
        if locale is not None:
            settings.locale = locale
        if opening_balance_minor is not None:
            settings.opening_balance_minor = opening_balance_minor
        if opening_balance_date is not None:
            settings.opening_balance_date = opening_balance_date
        self.repo.save(settings)
        return settings
