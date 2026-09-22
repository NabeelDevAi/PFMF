"""transactions

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-11

Matches architecture doc §5's DDL exactly, including both CHECK
constraints -- these are the DB-level backstop; the service layer
(TransactionService) validates the same rules first so violations surface
as named error codes (transaction.end_before_start,
transaction.one_time_has_end_date) instead of a raw IntegrityError.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "transactions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "scenario_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scenarios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column(
            "direction",
            postgresql.ENUM("income", "expense", name="direction", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "category_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("categories.id"),
            nullable=True,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "recurrence",
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
            nullable=False,
        ),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("amount_minor > 0", name="amount_positive"),
        sa.CheckConstraint("end_date IS NULL OR end_date >= start_date", name="valid_range"),
        sa.CheckConstraint(
            "recurrence <> 'one_time' OR end_date IS NULL", name="one_time_has_no_end"
        ),
    )
    op.create_index("ix_transactions_scenario_id", "transactions", ["scenario_id"])
    op.create_index("ix_transactions_user_id", "transactions", ["user_id"])


def downgrade() -> None:
    op.drop_table("transactions")
