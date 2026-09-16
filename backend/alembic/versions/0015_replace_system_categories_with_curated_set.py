"""replace system categories with curated set

Revision ID: 0015
Revises: 0014
Create Date: 2026-09-16

Product decision, found while verifying the transaction Add/Edit/Delete
screens against the Figma category picker: the design's 12 categories
(salary, freelance, business, housing, loans, bills, subscriptions,
everyday, transport, fuel, health, other) don't match migration 0004's
original 20 seeded keys at all. Replaces the system category set
wholesale to match the design exactly, rather than trying to map one
onto the other. Safe -- categories.user_id/transactions.category_id and
scenario_overlays.ovr_category_id are ON DELETE SET NULL (migration
0011), so any reference to a removed key just becomes uncategorized,
and there's no real user data yet to preserve.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0015"
down_revision: str | Sequence[str] | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

categories = sa.table(
    "categories",
    sa.column("id", postgresql.UUID(as_uuid=True)),
    sa.column("user_id", postgresql.UUID(as_uuid=True)),
    sa.column("key", sa.Text()),
    sa.column("name", sa.Text()),
    sa.column(
        "direction", postgresql.ENUM("income", "expense", name="direction", create_type=False)
    ),
    sa.column("sort_order", sa.Integer()),
)

# (key, direction, sort_order) -- exactly the 12 categories in the Figma
# category-picker mockup, in the grid's own order. The client owns the
# translated label and icon for every key.
NEW_SYSTEM_CATEGORIES: list[tuple[str, str, int]] = [
    ("salary", "income", 0),
    ("freelance", "income", 1),
    ("business", "income", 2),
    ("housing", "expense", 0),
    ("loans", "expense", 1),
    ("bills", "expense", 2),
    ("subscriptions", "expense", 3),
    ("everyday", "expense", 4),
    ("transport", "expense", 5),
    ("fuel", "expense", 6),
    ("health", "expense", 7),
    ("other", "expense", 8),
]

# The exact 20 keys migration 0004 originally seeded -- kept here only so
# downgrade() can restore them precisely.
OLD_SYSTEM_CATEGORIES: list[tuple[str, str, int]] = [
    ("salary", "income", 0),
    ("bonus", "income", 1),
    ("rental_income", "income", 2),
    ("business_income", "income", 3),
    ("investment_income", "income", 4),
    ("other_income", "income", 5),
    ("rent", "expense", 0),
    ("utilities", "expense", 1),
    ("groceries", "expense", 2),
    ("transportation", "expense", 3),
    ("dining", "expense", 4),
    ("subscriptions", "expense", 5),
    ("insurance", "expense", 6),
    ("loan_payment", "expense", 7),
    ("savings_transfer", "expense", 8),
    ("entertainment", "expense", 9),
    ("healthcare", "expense", 10),
    ("education", "expense", 11),
    ("childcare", "expense", 12),
    ("other_expense", "expense", 13),
]


def upgrade() -> None:
    op.execute("DELETE FROM categories WHERE user_id IS NULL")
    op.bulk_insert(
        categories,
        [
            {
                "id": uuid.uuid4(),
                "user_id": None,
                "key": key,
                "name": None,
                "direction": direction,
                "sort_order": sort_order,
            }
            for key, direction, sort_order in NEW_SYSTEM_CATEGORIES
        ],
    )


def downgrade() -> None:
    op.execute("DELETE FROM categories WHERE user_id IS NULL")
    op.bulk_insert(
        categories,
        [
            {
                "id": uuid.uuid4(),
                "user_id": None,
                "key": key,
                "name": None,
                "direction": direction,
                "sort_order": sort_order,
            }
            for key, direction, sort_order in OLD_SYSTEM_CATEGORIES
        ],
    )
