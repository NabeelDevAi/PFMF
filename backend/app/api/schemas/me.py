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
    display_name: str | None = None
    currency_code: str | None = None
    locale: str | None = None
    current_balance_minor: int | None = None
    balance_as_of: date | None = None
