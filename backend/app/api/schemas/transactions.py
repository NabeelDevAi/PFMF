from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel

from app.domain.enums import Direction, Origin, Recurrence


class TransactionOut(BaseModel):
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
    origin: Origin
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_row(cls, txn, origin: Origin) -> TransactionOut:
        """`txn` is the ORM row; `origin` is computed separately (never
        stored -- see Origin's docstring), so this can't be a plain
        from_attributes model_validate(txn)."""
        return cls(
            id=txn.id,
            scenario_id=txn.scenario_id,
            name=txn.name,
            amount_minor=txn.amount_minor,
            direction=txn.direction,
            category_id=txn.category_id,
            notes=txn.notes,
            recurrence=txn.recurrence,
            start_date=txn.start_date,
            end_date=txn.end_date,
            origin=origin,
            created_at=txn.created_at,
            updated_at=txn.updated_at,
        )


class TransactionListOut(BaseModel):
    items: list[TransactionOut]


class TransactionCreate(BaseModel):
    name: str
    amount_minor: int
    direction: Direction
    recurrence: Recurrence
    start_date: date
    end_date: date | None = None
    category_id: uuid.UUID | None = None
    notes: str | None = None


class TransactionPatch(BaseModel):
    name: str | None = None
    amount_minor: int | None = None
    direction: Direction | None = None  # accepted only to detect+reject a change; never applied
    recurrence: Recurrence | None = None
    start_date: date | None = None
    end_date: date | None = None
    unset_end_date: bool = False
    category_id: uuid.UUID | None = None
    unset_category_id: bool = False
    notes: str | None = None
    unset_notes: bool = False
