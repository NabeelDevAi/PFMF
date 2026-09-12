from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel

from app.domain.enums import OverlayOp, Recurrence


class OverlayOut(BaseModel):
    id: uuid.UUID
    scenario_id: uuid.UUID
    base_transaction_id: uuid.UUID
    op: OverlayOp
    ovr_name: str | None
    ovr_amount_minor: int | None
    ovr_category_id: uuid.UUID | None
    ovr_recurrence: Recurrence | None
    ovr_start_date: date | None
    ovr_end_date: date | None
    unset_end_date: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class OverlayCreate(BaseModel):
    base_transaction_id: uuid.UUID
    op: OverlayOp
    ovr_name: str | None = None
    ovr_amount_minor: int | None = None
    ovr_category_id: uuid.UUID | None = None
    ovr_recurrence: Recurrence | None = None
    ovr_start_date: date | None = None
    ovr_end_date: date | None = None
    unset_end_date: bool = False


class OverlayPatch(BaseModel):
    ovr_name: str | None = None
    ovr_amount_minor: int | None = None
    ovr_category_id: uuid.UUID | None = None
    unset_category_id: bool = False
    ovr_recurrence: Recurrence | None = None
    ovr_start_date: date | None = None
    ovr_end_date: date | None = None
    # Three-state: None = don't touch, True = make open-ended, False =
    # explicitly clear a previously-set unset flag (e.g. after also
    # supplying a real ovr_end_date in the same request).
    unset_end_date: bool | None = None
