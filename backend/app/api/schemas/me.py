from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel


class SettingsOut(BaseModel):
    display_name: str | None
    currency_code: str
    locale: str
    opening_balance_minor: int
    opening_balance_date: date

    model_config = {"from_attributes": True}


class MeOut(BaseModel):
    id: uuid.UUID
    email: str
    created_at: datetime
    settings: SettingsOut

    model_config = {"from_attributes": True}


class SettingsPatch(BaseModel):
    display_name: str | None = None
    currency_code: str | None = None
    locale: str | None = None
    opening_balance_minor: int | None = None
    opening_balance_date: date | None = None
