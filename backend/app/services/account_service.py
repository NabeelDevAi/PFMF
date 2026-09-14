"""DELETE /me -- permanent account deletion (screen-flow F9). Distinct
from ResetService: this removes the login itself, not just the data
under it. Not in the architecture doc's locked §9 API surface -- a small
addition, same category as the refresh_tokens table and the other gaps
flagged in claude_docs/backend-plan/12-open-questions-and-future-hardening.md.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.repositories.user_repository import UserRepository


class AccountService:
    def __init__(self, db: Session) -> None:
        self.users = UserRepository(db)

    def delete_account(self, user_id: uuid.UUID) -> None:
        user = self.users.get_by_id(user_id)
        if user is None:
            raise APIError("resource.not_found")
        # Cascades everything -- see UserRepository.delete()'s docstring.
        # Any access token already issued stops working the instant this
        # commits: get_current_user looks the user up by id on every
        # request and treats a missing user as auth.token_invalid, so no
        # separate token blocklist is needed for this.
        self.users.delete(user)
