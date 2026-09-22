"""scenario_overlays

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-12

Matches architecture doc §5's DDL exactly. No user_id column, unlike
transactions/scenarios -- overlays are always reached through their
scenario, and the scenario itself is already user-scoped (the service
layer fetches and ownership-checks the scenario first, then queries
overlays by scenario_id).

Direction is deliberately absent from the ovr_* columns: it's not
overridable (architecture §5) -- turning an income into an expense is a
different transaction, not a patch.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0010"
down_revision: str | Sequence[str] | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scenario_overlays",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "scenario_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scenarios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "base_transaction_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("transactions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "op",
            postgresql.ENUM("exclude", "override", name="overlay_op", create_type=False),
            nullable=False,
        ),
        sa.Column("ovr_name", sa.Text(), nullable=True),
        sa.Column("ovr_amount_minor", sa.BigInteger(), nullable=True),
        sa.Column(
            "ovr_category_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("categories.id"),
            nullable=True,
        ),
        sa.Column(
            "ovr_recurrence",
            postgresql.ENUM(
                "one_time",
                "weekly",
                "biweekly",
                "monthly",
                "quarterly",
                "semiannual",
                "annual",
                name="recurrence",
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column("ovr_start_date", sa.Date(), nullable=True),
        sa.Column("ovr_end_date", sa.Date(), nullable=True),
        sa.Column("unset_end_date", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "ovr_amount_minor IS NULL OR ovr_amount_minor > 0", name="ovr_amount_positive"
        ),
        sa.UniqueConstraint(
            "scenario_id", "base_transaction_id", name="uq_scenario_overlays_target"
        ),
    )
    op.create_index("ix_scenario_overlays_scenario_id", "scenario_overlays", ["scenario_id"])


def downgrade() -> None:
    op.drop_table("scenario_overlays")
