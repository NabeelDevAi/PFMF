"""seed system categories

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-09

Data migration, not application startup (backend-plan/03 §3). System
categories carry user_id NULL and a stable `key`; the Flutter client
translates by key, never displaying this data raw.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
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

# (key, direction, sort_order). Starter set covering RFP §4.3's examples
# plus common cases; the client owns the translated label for every key.
SYSTEM_CATEGORIES: list[tuple[str, str, int]] = [
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
            for key, direction, sort_order in SYSTEM_CATEGORIES
        ],
    )


def downgrade() -> None:
    op.execute("DELETE FROM categories WHERE user_id IS NULL")
