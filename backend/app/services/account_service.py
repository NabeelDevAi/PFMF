"""DELETE /me -- permanent account deletion (screen-flow F9). Distinct
from ResetService: this removes the login itself, not just the data
under it. Not in the architecture doc's locked §9 API surface -- a small
addition, same category as the refresh_tokens table and the other gaps
flagged in claude_docs/backend-plan/12-open-questions-and-future-hardening.md.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session

from app.core.avatar_storage import delete_avatar
from app.core.errors import APIError
from app.repositories.user_repository import UserRepository
from app.repositories.user_settings_repository import UserSettingsRepository

logger = logging.getLogger("pfmf.auth")


class AccountService:
    def __init__(self, db: Session) -> None:
        self.users = UserRepository(db)
        self.settings = UserSettingsRepository(db)

    def delete_account(self, user_id: uuid.UUID) -> None:
        user = self.users.get_by_id(user_id)
        if user is None:
            raise APIError("resource.not_found")
        # A DB row cascades automatically (ON DELETE CASCADE); a file on
        # disk does not -- read the filename before the row disappears,
        # then remove it explicitly, or it just orphans on disk forever.
        settings = self.settings.get_by_user_id(user_id)
        avatar_filename = settings.avatar_filename if settings is not None else None
        # Cascades everything -- see UserRepository.delete()'s docstring.
        # Any access token already issued stops working the instant this
        # commits: get_current_user looks the user up by id on every
        # request and treats a missing user as auth.token_invalid, so no
        # separate token blocklist is needed for this.
        self.users.delete(user)
        delete_avatar(avatar_filename)
        logger.info("account deleted", extra={"user_id": user_id})
