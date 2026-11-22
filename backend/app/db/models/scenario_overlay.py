from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base
from app.db.types import pg_enum
from app.domain.enums import OverlayOp, Recurrence, RecurrenceUnit


class ScenarioOverlay(Base):
    """How a derived scenario modifies an inherited Base transaction
    (architecture §5). `apply_patch` semantics: each `ovr_*` field is used
    when non-NULL, otherwise the Base value; `unset_end_date=true` forces
    `end_date = NULL`, solving the NULL-vs-not-overridden ambiguity for
    the one nullable overridable field.

    No `user_id` -- see this migration's docstring for why.
    """

    __tablename__ = "scenario_overlays"
    __table_args__ = (
        CheckConstraint(
            "ovr_amount_minor IS NULL OR ovr_amount_minor > 0", name="ovr_amount_positive"
        ),
        UniqueConstraint("scenario_id", "base_transaction_id", name="uq_scenario_overlays_target"),
        # Same rule as transactions: the override interval/unit exist exactly
        # when the overridden recurrence is `custom`.
        CheckConstraint(
            "ovr_recurrence IS NULL OR ovr_recurrence <> 'custom' OR "
            "(ovr_recurrence_interval IS NOT NULL AND ovr_recurrence_unit IS NOT NULL)",
            name="ovr_custom_has_interval_and_unit",
        ),
        CheckConstraint(
            "COALESCE(ovr_recurrence::text, '') = 'custom' OR "
            "(ovr_recurrence_interval IS NULL AND ovr_recurrence_unit IS NULL)",
            name="ovr_only_custom_has_interval_and_unit",
        ),
        CheckConstraint(
            "ovr_recurrence_interval IS NULL OR ovr_recurrence_interval BETWEEN 1 AND 999",
            name="ovr_recurrence_interval_range",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    scenario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scenarios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    base_transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transactions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    op: Mapped[OverlayOp] = mapped_column(pg_enum(OverlayOp, "overlay_op"), nullable=False)

    ovr_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    ovr_amount_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    ovr_category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )
    ovr_recurrence: Mapped[Recurrence | None] = mapped_column(
        pg_enum(Recurrence, "recurrence"), nullable=True
    )
    ovr_recurrence_interval: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ovr_recurrence_unit: Mapped[RecurrenceUnit | None] = mapped_column(
        pg_enum(RecurrenceUnit, "recurrence_unit"), nullable=True
    )
    ovr_start_date: Mapped[date | None] = mapped_column(nullable=True)
    ovr_end_date: Mapped[date | None] = mapped_column(nullable=True)
    unset_end_date: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
