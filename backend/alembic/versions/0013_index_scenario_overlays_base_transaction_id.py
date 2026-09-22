"""index scenario_overlays.base_transaction_id

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-15

GET /v1/transactions/{id}/dependents (architecture §6.3/§9, build spec
§10.4) is a lookup keyed on base_transaction_id alone. The existing
UniqueConstraint("scenario_id", "base_transaction_id") gives a composite
index with scenario_id as the leading column, which Postgres can't use
for that lookup -- the build spec explicitly calls for this to be
"backed by one indexed query on scenario_overlays.base_transaction_id",
so it needs its own index.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0013"
down_revision: str | Sequence[str] | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_scenario_overlays_base_transaction_id", "scenario_overlays", ["base_transaction_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_scenario_overlays_base_transaction_id", table_name="scenario_overlays")
