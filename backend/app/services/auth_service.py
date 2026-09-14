"""Registration, login, refresh rotation, logout, and the password-reset
token flow. See backend-plan/06-services-module.md and 09-auth-and-security.md.
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
from app.repositories.password_reset_token_repository import PasswordResetTokenRepository
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.scenario_repository import ScenarioRepository
from app.repositories.user_repository import UserRepository
from app.repositories.user_settings_repository import UserSettingsRepository
from app.services.password_reset_sender import ConsolePasswordResetSender, PasswordResetSender

MIN_PASSWORD_LENGTH = 8

logger = logging.getLogger("pfmf.auth")


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str


class AuthService:
    def __init__(
        self, db: Session, *, password_reset_sender: PasswordResetSender | None = None
    ) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.settings_repo = UserSettingsRepository(db)
        self.scenarios = ScenarioRepository(db)
        self.refresh_tokens = RefreshTokenRepository(db)
        self.reset_tokens = PasswordResetTokenRepository(db)
        self.password_reset_sender = password_reset_sender or ConsolePasswordResetSender()

    def register(self, *, email: str, password: str) -> TokenPair:
        _check_password_policy(password)
        if self.users.get_by_email(email) is not None:
            raise APIError("auth.email_taken", {"field": "email"})

        user = self.users.create(email=email, password_hash=hash_password(password))
        # Opening balance date defaults to today; onboarding (PATCH /me/settings)
        # is expected to set the real value. The engine never reads a clock --
        # this is a service, so it's allowed to.
        self.settings_repo.create_default(user_id=user.id, opening_balance_date=date.today())
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

    def request_password_reset(self, *, email: str) -> None:
        user = self.users.get_by_email(email)
        if user is None:
            return  # never reveal whether an email is registered

        settings = get_settings()
        raw_token = generate_refresh_token()
        expires_at = datetime.now(UTC) + timedelta(minutes=settings.password_reset_ttl_minutes)
        self.reset_tokens.create(
            user_id=user.id, token_hash=hash_token(raw_token), expires_at=expires_at
        )
        self.password_reset_sender.send(email=email, token=raw_token)

    def confirm_password_reset(self, *, token: str, new_password: str) -> None:
        _check_password_policy(new_password)

        record = self.reset_tokens.get_by_hash(hash_token(token))
        if record is None or record.used_at is not None or record.expires_at < datetime.now(UTC):
            raise APIError("auth.reset_token_invalid")

        user = self.users.get_by_id(record.user_id)
        if user is None:
            raise APIError("auth.reset_token_invalid")

        self.users.update_password(user, hash_password(new_password))
        self.reset_tokens.mark_used(record)

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
