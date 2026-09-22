"""users soft delete

Revision ID: 0017
Revises: 0016
Create Date: 2026-09-16

DELETE /me (screen-flow F9, Settings > Delete account): product decision
-- appears as a hard delete to the user (can't log in, token stops
working immediately, email is free for a new registration right away),
but the row and everything it owns physically stays untouched. Phase 2
schedules the real purge (UserRepository.delete(), already built,
unused in Phase 1). See 12-open-questions-and-future-hardening.md.

Swaps the plain `uq_users_email` constraint for a partial unique index
so a soft-deleted row's email doesn't block a brand-new registration
with the same address -- uniqueness only applies among active
(deleted_at IS NULL) rows.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0017"
down_revision: str | Sequence[str] | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True))
    op.drop_constraint("uq_users_email", "users", type_="unique")
    op.create_index(
        "uq_users_email_active",
        "users",
        ["email"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_users_email_active", table_name="users")
    op.create_unique_constraint("uq_users_email", "users", ["email"])
    op.drop_column("users", "deleted_at")
