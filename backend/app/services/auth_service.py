"""Registration, login, refresh rotation, logout, and changing a
password while logged in. See backend-plan/06-services-module.md and
09-auth-and-security.md.

No forgot/reset-password-via-email flow in Phase 1 -- that needs a real
transactional email provider (an unresolved external dependency),
deferred to Phase 2 by explicit product decision. A user who forgets
their password has no self-service recovery in Phase 1; they can only
change a password they already know, while logged in.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import APIError
from app.core.security import (
    encode_access_token,
    generate_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.scenario_repository import ScenarioRepository
from app.repositories.user_repository import UserRepository
from app.repositories.user_settings_repository import UserSettingsRepository

MIN_PASSWORD_LENGTH = 8

logger = logging.getLogger("pfmf.auth")


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.settings_repo = UserSettingsRepository(db)
        self.scenarios = ScenarioRepository(db)
        self.refresh_tokens = RefreshTokenRepository(db)

    def register(self, *, email: str, password: str, name: str) -> TokenPair:
        _check_password_policy(password)
        if self.users.get_by_email(email) is not None:
            raise APIError("auth.email_taken", {"field": "email"})

        user = self.users.create(email=email, password_hash=hash_password(password))
        # balance_as_of defaults to today; onboarding is expected to set the
        # real Current Cash Balance value. The engine never reads a clock --
        # this is a service, so it's allowed to.
        self.settings_repo.create_default(
            user_id=user.id, balance_as_of=date.today(), display_name=name
        )
        self.scenarios.create_base(user_id=user.id)

        logger.info("user registered", extra={"user_id": user.id})
        return self._issue_tokens(user.id, family_id=uuid.uuid4())

    def login(self, *, email: str, password: str) -> TokenPair:
        user = self.users.get_by_email(email)
        if user is None or not verify_password(user.password_hash, password):
            # Never log the attempted email -- there is nothing to
            # correlate a failure to without it, by design.
            logger.warning("login failed")
            raise APIError("auth.invalid_credentials")
        logger.info("login succeeded", extra={"user_id": user.id})
        return self._issue_tokens(user.id, family_id=uuid.uuid4())

    def refresh(self, *, refresh_token: str) -> TokenPair:
        token = self.refresh_tokens.get_by_hash(hash_token(refresh_token))
        if token is None or token.revoked_at is not None:
            raise APIError("auth.token_invalid")

        if token.used_at is not None:
            # Reuse of an already-rotated-away-from token: standard replay
            # signal. Revoke the whole family -- including any legitimately
            # newer token in it, since we can no longer tell which party
            # holds it. Committed here, not left to the router: the
            # exception raised right after skips the router's normal
            # post-call commit, and this revocation must survive that.
            self.refresh_tokens.revoke_family(token.family_id)
            self.db.commit()
            # Security-relevant: this is the actual replay signal, worth
            # its own log line distinct from an ordinary invalid token.
            logger.warning(
                "refresh token reuse detected, family revoked",
                extra={"user_id": token.user_id, "family_id": token.family_id},
            )
            raise APIError("auth.token_invalid")

        if token.expires_at < datetime.now(UTC):
            raise APIError("auth.token_invalid")

        self.refresh_tokens.mark_used(token)
        return self._issue_tokens(token.user_id, family_id=token.family_id)

    def logout(self, *, refresh_token: str) -> None:
        token = self.refresh_tokens.get_by_hash(hash_token(refresh_token))
        if token is not None:
            self.refresh_tokens.revoke_family(token.family_id)
        # Idempotent: an already-invalid or unknown token still "succeeds" --
        # the caller's intent (be logged out) is already satisfied.

    def change_password(
        self, user_id: uuid.UUID, *, current_password: str, new_password: str
    ) -> None:
        """The only way to change a password in Phase 1 -- requires an
        active session and the current password re-entered (never just a
        bare new-password field, which would let a hijacked-but-still-
        logged-in session lock the real owner out). Revokes every
        refresh-token family for this user, including the one that
        authenticated this very request: changing a password is exactly
        the moment every other session should stop working, and the
        client is expected to re-authenticate afterward."""
        user = self.users.get_by_id(user_id)
        if user is None:
            raise APIError("resource.not_found")
        if not verify_password(user.password_hash, current_password):
            raise APIError("auth.current_password_incorrect")

        _check_password_policy(new_password)
        self.users.update_password(user, hash_password(new_password))
        self.refresh_tokens.revoke_all_for_user(user_id)
        logger.info("password changed", extra={"user_id": user_id})

    def _issue_tokens(self, user_id: uuid.UUID, *, family_id: uuid.UUID) -> TokenPair:
        settings = get_settings()
        raw_refresh = generate_refresh_token()
        expires_at = datetime.now(UTC) + timedelta(days=settings.jwt_refresh_ttl_days)
        self.refresh_tokens.create(
            user_id=user_id,
            family_id=family_id,
            token_hash=hash_token(raw_refresh),
            expires_at=expires_at,
        )
        return TokenPair(access_token=encode_access_token(user_id), refresh_token=raw_refresh)


def _check_password_policy(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise APIError("auth.weak_password", {"field": "password"})
