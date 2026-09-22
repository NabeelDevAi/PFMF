"""rename to current_balance vocabulary

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-15

v1.1 of the architecture doc (D-04) formally separates the Current Cash
Balance (user-confirmed, never system-mutated) from the Projected
Balance (an engine output, not stored anywhere). This migration renames
the three columns that carried the old "opening balance" vocabulary to
match:

  user_settings.opening_balance_minor          -> current_balance_minor
  user_settings.opening_balance_date            -> balance_as_of
  scenarios.opening_balance_override_minor      -> current_balance_override_minor

Pure rename -- no data transformation, no new columns, no new
constraints. Never edited after merge (repo convention); if a future
change is needed, it goes in a new migration forward from here.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0012"
down_revision: str | Sequence[str] | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "user_settings", "opening_balance_minor", new_column_name="current_balance_minor"
    )
    op.alter_column("user_settings", "opening_balance_date", new_column_name="balance_as_of")
    op.alter_column(
        "scenarios",
        "opening_balance_override_minor",
        new_column_name="current_balance_override_minor",
    )


def downgrade() -> None:
    op.alter_column(
        "scenarios",
        "current_balance_override_minor",
        new_column_name="opening_balance_override_minor",
    )
    op.alter_column("user_settings", "balance_as_of", new_column_name="opening_balance_date")
    op.alter_column(
        "user_settings", "current_balance_minor", new_column_name="opening_balance_minor"
    )
