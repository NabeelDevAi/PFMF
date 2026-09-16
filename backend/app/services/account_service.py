"""DELETE /me -- account deletion (screen-flow F9). Distinct from
ResetService: this removes the login itself, not just the data under
it. Not in the architecture doc's locked §9 API surface -- a small
addition, same category as the refresh_tokens table and the other gaps
flagged in claude_docs/backend-plan/12-open-questions-and-future-hardening.md.

Product decision: this is a **soft** delete. It looks and behaves like
a hard delete from the user's side -- they can't log in again, any
already-issued token stops working immediately, and their email is
free for a brand-new registration right away (UserRepository's
deleted_at filtering + the partial unique index, migration 0017) -- but
the row and everything it owns physically stays untouched. Phase 2
schedules the real purge (UserRepository.delete(), already built,
intentionally unused here); see
12-open-questions-and-future-hardening.md for the full record.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository

logger = logging.getLogger("pfmf.auth")


class AccountService:
    def __init__(self, db: Session) -> None:
        self.users = UserRepository(db)
        self.refresh_tokens = RefreshTokenRepository(db)

    def delete_account(self, user_id: uuid.UUID) -> None:
        user = self.users.get_by_id(user_id)
        if user is None:
            raise APIError("resource.not_found")
        self.users.soft_delete(user)
        # Nothing cascades on a soft delete -- the row is still there,
        # so a still-valid refresh token would otherwise keep minting
        # new access tokens for an account that's supposed to be gone.
        # Access tokens need no separate handling: get_current_user
        # re-looks-up the user by id on every request, and soft_delete
        # makes that lookup fail (auth.token_invalid) immediately.
        self.refresh_tokens.revoke_all_for_user(user_id)
        logger.info("account soft-deleted", extra={"user_id": user_id})
