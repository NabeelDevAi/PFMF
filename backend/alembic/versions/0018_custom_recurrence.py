"""custom recurrence

Revision ID: 0018
Revises: 0017
Create Date: 2026-11-22

UAT-004 / D-08 amended: a bounded "every N days / weeks / months / years"
recurrence. Adds the `custom` value to the `recurrence` enum, a new
`recurrence_unit` enum, and the interval + unit columns on `transactions`
(and the matching `ovr_*` columns on `scenario_overlays`), with CHECK
constraints so the DB itself guarantees: custom has both fields, every other
recurrence has neither, and the interval is 1..999. Existing rows are
untouched (none can be custom).

Downgrade removes the columns and the enum value again. Postgres cannot drop
a single enum label, so the type is rebuilt; the downgrade therefore fails
(by design, nothing is silently rewritten) if any row still uses `custom`.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0018"
down_revision: str | Sequence[str] | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_VALUES = ("one_time", "weekly", "biweekly", "monthly", "quarterly", "semiannual", "annual")


def upgrade() -> None:
    # A new enum label cannot be used in the transaction that adds it, so add
    # it in its own autocommit block before the constraints that name it.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE recurrence ADD VALUE IF NOT EXISTS 'custom'")

    unit = postgresql.ENUM(
        "day", "week", "month", "year", name="recurrence_unit", create_type=False
    )
    unit.create(op.get_bind(), checkfirst=True)

    op.add_column("transactions", sa.Column("recurrence_interval", sa.Integer(), nullable=True))
    op.add_column("transactions", sa.Column("recurrence_unit", unit, nullable=True))
    op.create_check_constraint(
        "custom_has_interval_and_unit",
        "transactions",
        "recurrence <> 'custom' OR "
        "(recurrence_interval IS NOT NULL AND recurrence_unit IS NOT NULL)",
    )
    op.create_check_constraint(
        "only_custom_has_interval_and_unit",
        "transactions",
        "recurrence = 'custom' OR (recurrence_interval IS NULL AND recurrence_unit IS NULL)",
    )
    op.create_check_constraint(
        "recurrence_interval_range",
        "transactions",
        "recurrence_interval IS NULL OR recurrence_interval BETWEEN 1 AND 999",
    )

    op.add_column(
        "scenario_overlays", sa.Column("ovr_recurrence_interval", sa.Integer(), nullable=True)
    )
    op.add_column("scenario_overlays", sa.Column("ovr_recurrence_unit", unit, nullable=True))
    op.create_check_constraint(
        "ovr_custom_has_interval_and_unit",
        "scenario_overlays",
        "ovr_recurrence IS NULL OR ovr_recurrence <> 'custom' OR "
        "(ovr_recurrence_interval IS NOT NULL AND ovr_recurrence_unit IS NOT NULL)",
    )
    op.create_check_constraint(
        "ovr_only_custom_has_interval_and_unit",
        "scenario_overlays",
        "COALESCE(ovr_recurrence::text, '') = 'custom' OR "
        "(ovr_recurrence_interval IS NULL AND ovr_recurrence_unit IS NULL)",
    )
    op.create_check_constraint(
        "ovr_recurrence_interval_range",
        "scenario_overlays",
        "ovr_recurrence_interval IS NULL OR ovr_recurrence_interval BETWEEN 1 AND 999",
    )


def downgrade() -> None:
    op.drop_constraint("ovr_recurrence_interval_range", "scenario_overlays", type_="check")
    op.drop_constraint("ovr_only_custom_has_interval_and_unit", "scenario_overlays", type_="check")
    op.drop_constraint("ovr_custom_has_interval_and_unit", "scenario_overlays", type_="check")
    op.drop_column("scenario_overlays", "ovr_recurrence_unit")
    op.drop_column("scenario_overlays", "ovr_recurrence_interval")

    op.drop_constraint("recurrence_interval_range", "transactions", type_="check")
    op.drop_constraint("only_custom_has_interval_and_unit", "transactions", type_="check")
    op.drop_constraint("custom_has_interval_and_unit", "transactions", type_="check")
    op.drop_column("transactions", "recurrence_unit")
    op.drop_column("transactions", "recurrence_interval")
    op.execute("DROP TYPE recurrence_unit")

    # Rebuild `recurrence` without 'custom'. The one_time check mentions the
    # column, so drop and recreate it around the type change.
    op.drop_constraint("one_time_has_no_end", "transactions", type_="check")
    op.execute("ALTER TYPE recurrence RENAME TO recurrence_with_custom")
    old = postgresql.ENUM(*_OLD_VALUES, name="recurrence")
    old.create(op.get_bind())
    op.execute(
        "ALTER TABLE transactions ALTER COLUMN recurrence TYPE recurrence "
        "USING recurrence::text::recurrence"
    )
    op.execute(
        "ALTER TABLE scenario_overlays ALTER COLUMN ovr_recurrence TYPE recurrence "
        "USING ovr_recurrence::text::recurrence"
    )
    op.execute("DROP TYPE recurrence_with_custom")
    op.create_check_constraint(
        "one_time_has_no_end", "transactions", "recurrence <> 'one_time' OR end_date IS NULL"
    )
