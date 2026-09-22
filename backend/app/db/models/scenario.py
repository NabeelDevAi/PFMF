from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func, text

from app.db.base import Base


class Scenario(Base):
    """A named set of financial assumptions. Exactly one per user has
    is_base = true, enforced by the partial unique index below and backed
    up structurally in the service layer (Base can never be deleted or
    archived). See architecture doc §5, §5.1.

    Only the columns needed through milestone M2 (register creates a
    user's Base scenario) are defined here -- transactions/overlays land
    with milestones M3/M4.
    """

    __tablename__ = "scenarios"
    __table_args__ = (
        Index("one_base_per_user", "user_id", unique=True, postgresql_where=text("is_base")),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    is_base: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    current_balance_override_minor: Mapped[int | None] = mapped_column(
        nullable=True
    )  # NULL = inherit
    archived_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )
