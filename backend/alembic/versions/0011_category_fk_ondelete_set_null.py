"""category fk ondelete set null

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-15

Bug found while building PATCH/DELETE /v1/categories/{id}: neither
transactions.category_id nor scenario_overlays.ovr_category_id had an
ON DELETE rule against categories (default RESTRICT). That's harmless
for the single-category delete this migration's sibling change guards
(CategoryService.delete checks usage first and raises category.in_use
before ever reaching the DB), but it's a real bug on the *account*
deletion path (DELETE /v1/me, app/services/account_service.py): deleting
a user cascades to their own categories (categories.user_id ON DELETE
CASCADE) independently of the cascade that removes their transactions
and overlays (via scenarios.user_id / scenario_id ON DELETE CASCADE).
Postgres doesn't guarantee which of a table's several cascade paths
fires first, so whenever a user had ever pointed a transaction or an
overlay's override at one of their own custom categories, account
deletion could fail with an unhandled IntegrityError -- intermittently,
depending on trigger firing order, which is exactly how this surfaced:
as stale rows a plain `DELETE FROM users` couldn't clear during test
cleanup.

SET NULL (not CASCADE) on both: losing a category should orphan the
row's category reference, not delete the transaction/overlay itself --
both columns are already nullable, and the app already treats "no
category" as a normal state (TransactionPatch.unset_category_id, a bare
create/update with no category_id at all).
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0011"
down_revision: str | Sequence[str] | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("transactions_category_id_fkey", "transactions", type_="foreignkey")
    op.create_foreign_key(
        "transactions_category_id_fkey",
        "transactions",
        "categories",
        ["category_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.drop_constraint(
        "scenario_overlays_ovr_category_id_fkey", "scenario_overlays", type_="foreignkey"
    )
    op.create_foreign_key(
        "scenario_overlays_ovr_category_id_fkey",
        "scenario_overlays",
        "categories",
        ["ovr_category_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "scenario_overlays_ovr_category_id_fkey", "scenario_overlays", type_="foreignkey"
    )
    op.create_foreign_key(
        "scenario_overlays_ovr_category_id_fkey",
        "scenario_overlays",
        "categories",
        ["ovr_category_id"],
        ["id"],
    )
    op.drop_constraint("transactions_category_id_fkey", "transactions", type_="foreignkey")
    op.create_foreign_key(
        "transactions_category_id_fkey", "transactions", "categories", ["category_id"], ["id"]
    )
