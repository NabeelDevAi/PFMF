from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.user import User


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, user_id: uuid.UUID) -> User | None:
        # deleted_at IS NULL -- a soft-deleted account must be invisible
        # to every ordinary lookup (auth, exports, ...); see soft_delete().
        return self.db.scalar(select(User).where(User.id == user_id, User.deleted_at.is_(None)))

    def get_by_email(self, email: str) -> User | None:
        # CITEXT on the column already makes this comparison case-insensitive.
        # Same deleted_at filter as get_by_id -- a soft-deleted email is
        # free to be reused by a brand-new registration (the partial
        # unique index, migration 0017, only enforces uniqueness among
        # non-deleted rows).
        return self.db.scalar(select(User).where(User.email == email, User.deleted_at.is_(None)))

    def create(self, *, email: str, password_hash: str) -> User:
        user = User(email=email, password_hash=password_hash)
        self.db.add(user)
        self.db.flush()  # populate user.id without committing the transaction
        return user

    def update_password(self, user: User, password_hash: str) -> None:
        user.password_hash = password_hash
        self.db.flush()

    def soft_delete(self, user: User) -> None:
        """DELETE /me's actual behavior in Phase 1 (product decision):
        appears as a hard delete from the user's side -- can't log in,
        any already-issued token stops working immediately (get_by_id
        above), the email is immediately free for a new registration --
        but the row and everything it owns physically stays untouched.
        Phase 2 schedules the real purge; see
        12-open-questions-and-future-hardening.md. `delete()` below is
        the method that eventual job calls -- already built, already
        tested, just not wired to anything in Phase 1."""
        user.deleted_at = datetime.now(UTC)
        self.db.flush()

    def delete(self, user: User) -> None:
        """The real, permanent delete -- reserved for Phase 2's scheduled
        purge job (see soft_delete() above), not called anywhere in
        Phase 1. Cascades to everything the user owns -- user_settings,
        categories, scenarios (and transitively their transactions and
        overlays), refresh_tokens -- via each table's own ON DELETE
        CASCADE. The one thing that does NOT cascade: a profile photo on
        disk (app/core/avatar_storage.py) -- whatever eventually calls
        this must also delete_avatar(settings.avatar_filename) first,
        the same way AccountService used to before soft-delete."""
        self.db.delete(user)
        self.db.flush()
