from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import CHAR, BigInteger, Date, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class UserSettings(Base):
    """Currency, locale, and the Current Cash Balance (D-04): a figure
    the user confirmed, dated by `balance_as_of`, never mutated by the
    system. Distinct from the Projected Balance, which is an engine
    output and isn't stored anywhere. One row per user. See architecture
    doc §5."""

    __tablename__ = "user_settings"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar_filename: Mapped[str | None] = mapped_column(Text, nullable=True)
    currency_code: Mapped[str] = mapped_column(CHAR(3), nullable=False, server_default="SAR")
    locale: Mapped[str] = mapped_column(Text, nullable=False, server_default="en")  # 'en' | 'ar'
    current_balance_minor: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default="0"
    )
    balance_as_of: Mapped[date] = mapped_column(Date, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )

    @property
    def avatar_url(self) -> str | None:
        """A path, not a stored value -- built from `avatar_filename` so
        SettingsOut (from_attributes=True) can read it like any other
        field. Relative, matching how every other client-facing value in
        this API leaves formatting to the client: it prepends its own
        configured base URL (the same one used for API calls, without
        the /v1 prefix -- this route isn't versioned)."""
        if self.avatar_filename is None:
            return None
        return f"/static/avatars/{self.avatar_filename}"
