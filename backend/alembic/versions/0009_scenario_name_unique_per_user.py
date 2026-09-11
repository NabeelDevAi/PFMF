"""scenario name unique per user

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-11

Another small addition beyond the architecture doc's original §5 DDL,
same category as the refresh_tokens/password_reset_tokens tables: the
error registry (backend-plan/07) already defines scenario.name_taken
(409, "Duplicate scenario name for this user"), which implies a
uniqueness rule the DDL never actually declared. Enforced here as the
DB-level backstop; ScenarioService checks it first so a collision
surfaces as that named code, not a raw IntegrityError.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0009"
down_revision: str | Sequence[str] | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint("uq_scenarios_user_id_name", "scenarios", ["user_id", "name"])


def downgrade() -> None:
    op.drop_constraint("uq_scenarios_user_id_name", "scenarios", type_="unique")
