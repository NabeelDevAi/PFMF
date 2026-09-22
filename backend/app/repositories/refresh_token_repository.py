from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.db.models.refresh_token import RefreshToken


class RefreshTokenRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self, *, user_id: uuid.UUID, family_id: uuid.UUID, token_hash: str, expires_at: datetime
    ) -> RefreshToken:
        token = RefreshToken(
            user_id=user_id, family_id=family_id, token_hash=token_hash, expires_at=expires_at
        )
        self.db.add(token)
        self.db.flush()
        return token

    def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        return (
            self.db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).one_or_none()
        )

    def mark_used(self, token: RefreshToken) -> None:
        token.used_at = datetime.now(UTC)
        self.db.flush()

    def revoke_family(self, family_id: uuid.UUID) -> None:
        """Revokes every token in the family, including ones issued after
        the one that triggered this -- see RefreshToken's docstring."""
        self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
        self.db.flush()

    def revoke_all_for_user(self, user_id: uuid.UUID) -> None:
        """Every family, not just one -- used by AuthService.change_password:
        changing a password is exactly the moment every other session
        (device, browser, stolen token) should stop working, not just the
        one that triggered the change."""
        self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
        self.db.flush()
