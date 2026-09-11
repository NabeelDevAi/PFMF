from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class ScenarioOut(BaseModel):
    id: uuid.UUID
    name: str
    is_base: bool
    opening_balance_override_minor: int | None
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ScenarioListOut(BaseModel):
    items: list[ScenarioOut]


class ScenarioCreate(BaseModel):
    name: str
    opening_balance_override_minor: int | None = None


class ScenarioPatch(BaseModel):
    name: str | None = None
    opening_balance_override_minor: int | None = None
    # Distinguishes "don't touch the override" (both fields False/None)
    # from "clear it back to inheriting from user_settings" -- the same
    # NULL-vs-not-set ambiguity the architecture doc solves for overlays'
    # unset_end_date.
    unset_opening_balance_override: bool = False


class ScenarioDuplicateRequest(BaseModel):
    name: str | None = None
