from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base
from app.db.types import pg_enum
from app.domain.enums import Direction


class Category(Base):
    """System categories have user_id NULL and are translated client-side
    by `key` (architecture §10). User categories carry free-text `name`
    stored as entered. See architecture doc §5."""

    __tablename__ = "categories"
    __table_args__ = (
        CheckConstraint(
            "(user_id IS NULL AND key IS NOT NULL AND name IS NULL) OR "
            "(user_id IS NOT NULL AND name IS NOT NULL AND key IS NULL)",
            name="category_naming",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    key: Mapped[str | None] = mapped_column(Text, nullable=True)  # system only
    name: Mapped[str | None] = mapped_column(Text, nullable=True)  # user-defined only
    direction: Mapped[Direction] = mapped_column(pg_enum(Direction, "direction"), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
