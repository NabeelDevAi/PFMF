from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import CITEXT, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class User(Base):
    """Identity and auth. See architecture doc §5."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    # Not unique=True here -- uniqueness is a partial index (email unique
    # only WHERE deleted_at IS NULL, migration 0017), not a plain
    # constraint, so a soft-deleted row's email can be reused by a new
    # registration. Same reasoning as scenarios.one_base_per_user.
    email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )
    # Soft-delete (product decision): DELETE /me sets this instead of
    # actually removing the row -- see UserRepository.soft_delete()'s
    # docstring. NULL means active; every ordinary lookup filters it out.
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)
