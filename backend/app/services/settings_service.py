from __future__ import annotations

import uuid
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.core.avatar_storage import delete_avatar, save_avatar
from app.core.config import get_settings
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
        avatar_base64: str | None = None,
        remove_avatar: bool = False,
    ) -> UserSettings:
        settings = self.get(user_id)
        if display_name is not None:
            settings.display_name = display_name
        if currency_code is not None:
            settings.currency_code = currency_code
        if locale is not None:
            settings.locale = locale
        if remove_avatar:
            delete_avatar(settings.avatar_filename)
            settings.avatar_filename = None
        elif avatar_base64 is not None:
            # Validate and write the new file *before* touching the old
            # one -- a rejected/failed upload must never destroy a photo
            # that was already working.
            new_filename = save_avatar(avatar_base64)
            delete_avatar(settings.avatar_filename)
            settings.avatar_filename = new_filename
        self.repo.save(settings)
        return settings

    def update_balance(
        self, user_id: uuid.UUID, *, current_balance_minor: int, balance_as_of: date
    ) -> UserSettings:
        """The *only* method allowed to write current_balance_minor /
        balance_as_of (D-04, architecture §9.1) -- backing PUT /me/balance,
        deliberately kept off SettingsService.patch() and its endpoint.
        No other code path in the app calls this."""
        if current_balance_minor < 0:
            raise APIError("balance.negative_not_allowed", {"field": "current_balance_minor"})

        today = date.today()
        if balance_as_of > today:
            raise APIError("balance.as_of_in_future", {"field": "balance_as_of"})

        max_age_years = get_settings().balance_as_of_max_age_years
        # Approximate years-to-days rather than a calendar year subtraction,
        # which would need leap-day handling for no real benefit -- this is
        # a soft backstop, not a precise boundary.
        oldest_allowed = today - timedelta(days=365 * max_age_years)
        if balance_as_of < oldest_allowed:
            raise APIError("balance.as_of_too_old", {"field": "balance_as_of"})

        settings = self.get(user_id)
        settings.current_balance_minor = current_balance_minor
        settings.balance_as_of = balance_as_of
        self.repo.save(settings)
        return settings
