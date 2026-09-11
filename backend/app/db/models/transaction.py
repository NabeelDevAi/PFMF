from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base
from app.db.types import pg_enum
from app.domain.enums import Direction, Recurrence


class Transaction(Base):
    """A recurring or one-time money movement *definition* -- a rule, not
    a record of something that happened (D-02). Belongs to exactly one
    scenario; `user_id` is denormalized alongside `scenario_id` so every
    query can be scoped by user_id directly, without a join. See
    architecture doc §5.

    Direction is deliberately not overridable after creation (enforced in
    TransactionService, not here) -- changing income <-> expense is
    semantically a different transaction.
    """

    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("amount_minor > 0", name="amount_positive"),
        CheckConstraint("end_date IS NULL OR end_date >= start_date", name="valid_range"),
        CheckConstraint("recurrence <> 'one_time' OR end_date IS NULL", name="one_time_has_no_end"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scenario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scenarios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    direction: Mapped[Direction] = mapped_column(pg_enum(Direction, "direction"), nullable=False)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recurrence: Mapped[Recurrence] = mapped_column(
        pg_enum(Recurrence, "recurrence"), nullable=False
    )
    start_date: Mapped[date] = mapped_column(nullable=False)
    end_date: Mapped[date | None] = mapped_column(nullable=True)  # NULL = open-ended
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )
