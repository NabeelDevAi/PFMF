from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class RefreshToken(Base):
    """Not in the architecture doc's original §5 DDL -- added here because
    the auth design (both prior docs) requires persisting refresh tokens:
    hashed, rotated on every use, and revocable as a whole family on reuse
    detection. See claude_docs/backend-plan/03-database-schema-and-migrations.md §2.

    `family_id` groups every token descended from one login. Revoking a
    family (on reuse detection, or on logout) sets revoked_at on every row
    that shares it, including ones issued after the compromised one --
    which is the correct, conservative response: we can no longer tell
    which party holds the legitimate latest token.
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(Text, unique=True, nullable=False, index=True)
    used_at: Mapped[datetime | None] = mapped_column(nullable=True)  # set when rotated away from
    revoked_at: Mapped[datetime | None] = mapped_column(nullable=True)  # set on the whole family
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
