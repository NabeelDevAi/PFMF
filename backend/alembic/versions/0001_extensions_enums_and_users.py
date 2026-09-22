"""extensions, enum types, and users

Revision ID: 0001
Revises:
Create Date: 2026-09-09

Creates the citext extension (needed for case-insensitive unique email),
gen_random_uuid() is built into Postgres core since v13 so no extension is
needed for it, and all three enum types from architecture doc §5 -- direction
and users now; recurrence and overlay_op aren't consumed by any table until
milestones M3/M4, but the architecture doc declares all three together, so
this migration does too.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")

    op.execute("CREATE TYPE direction AS ENUM ('income', 'expense')")
    op.execute(
        "CREATE TYPE recurrence AS ENUM "
        "('one_time','weekly','biweekly','monthly','quarterly','semiannual','annual')"
    )
    op.execute("CREATE TYPE overlay_op AS ENUM ('exclude', 'override')")

    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
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
    )
    op.create_unique_constraint("uq_users_email", "users", ["email"])


def downgrade() -> None:
    op.drop_table("users")
    op.execute("DROP TYPE overlay_op")
    op.execute("DROP TYPE recurrence")
    op.execute("DROP TYPE direction")
    op.execute("DROP EXTENSION IF EXISTS citext")
