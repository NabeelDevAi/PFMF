"""drop password_reset_tokens

Revision ID: 0014
Revises: 0013
Create Date: 2026-09-16

Product decision: no forgot-password/reset-password-via-email flow in
Phase 1 at all -- a logged-in user can only change their password
(PATCH /v1/me/password), never reset one without a session. That flow
needs a real transactional email provider, which is an unresolved
external dependency (backend-plan/09-auth-and-security.md); rather than
leave the whole request/confirm/token/sender flow built but unreachable,
it's removed cleanly now. Phase 2 re-adds this table fresh, informed by
whatever provider is chosen then, rather than resurrecting dormant
schema and code that predates that decision.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0014"
down_revision: str | Sequence[str] | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("password_reset_tokens")


def downgrade() -> None:
    op.create_table(
        "password_reset_tokens",
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
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("used_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])
    op.create_unique_constraint(
        "uq_password_reset_tokens_token_hash", "password_reset_tokens", ["token_hash"]
    )
    op.create_index("ix_password_reset_tokens_token_hash", "password_reset_tokens", ["token_hash"])
