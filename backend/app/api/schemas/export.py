from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel

from app.api.schemas.categories import CategoryOut
from app.api.schemas.me import SettingsOut
from app.api.schemas.overlays import OverlayOut
from app.api.schemas.scenarios import ScenarioOut
from app.domain.enums import Direction, Recurrence

if TYPE_CHECKING:
    from app.services.export_service import ExportData


class ExportUserOut(BaseModel):
    id: uuid.UUID
    email: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ExportTransactionOut(BaseModel):
    """Same fields as TransactionOut minus `origin` -- a raw row has no
    origin of its own, that's only meaningful through a resolved view
    (Origin's docstring in app.domain.enums)."""

    id: uuid.UUID
    scenario_id: uuid.UUID
    name: str
    amount_minor: int
    direction: Direction
    category_id: uuid.UUID | None
    notes: str | None
    recurrence: Recurrence
    start_date: date
    end_date: date | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ExportOut(BaseModel):
    user: ExportUserOut
    settings: SettingsOut
    categories: list[CategoryOut]
    scenarios: list[ScenarioOut]
    transactions: list[ExportTransactionOut]
    overlays: list[OverlayOut]

    @classmethod
    def from_data(cls, data: ExportData) -> ExportOut:
        return cls(
            user=ExportUserOut.model_validate(data.user),
            settings=SettingsOut.model_validate(data.settings),
            categories=[CategoryOut.model_validate(c) for c in data.categories],
            scenarios=[ScenarioOut.model_validate(s) for s in data.scenarios],
            transactions=[ExportTransactionOut.model_validate(t) for t in data.transactions],
            overlays=[OverlayOut.model_validate(o) for o in data.overlays],
        )
