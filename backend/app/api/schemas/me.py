from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel


class SettingsOut(BaseModel):
    display_name: str | None
    currency_code: str
    locale: str
    current_balance_minor: int
    balance_as_of: date

    model_config = {"from_attributes": True}


class MeOut(BaseModel):
    id: uuid.UUID
    email: str
    created_at: datetime
    settings: SettingsOut

    model_config = {"from_attributes": True}


class SettingsPatch(BaseModel):
    """Currency, locale, display name only. The Current Cash Balance is
    deliberately not settable here -- see BalanceUpdate / PUT /me/balance
    (architecture §9.1, D-04): keeping it off this endpoint is what makes
    "only one write path re-anchors every forecast" a structural fact
    rather than a convention."""

    display_name: str | None = None
    currency_code: str | None = None
    locale: str | None = None


class BalanceUpdate(BaseModel):
    current_balance_minor: int
    balance_as_of: date
