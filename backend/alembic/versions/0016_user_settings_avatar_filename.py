"""user_settings avatar_filename

Revision ID: 0016
Revises: 0015
Create Date: 2026-09-16

Profile photo (screen-flow F2), folded into the existing PATCH
/me/settings endpoint rather than a separate upload route, by explicit
product decision. Stores only a filename -- UserSettings.avatar_url
(a Python property, not a column) builds the servable path from it.
Local-disk storage; see app/core/avatar_storage.py's module docstring.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0016"
down_revision: str | Sequence[str] | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("user_settings", sa.Column("avatar_filename", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("user_settings", "avatar_filename")
