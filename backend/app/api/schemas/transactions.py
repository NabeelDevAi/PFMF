from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel

from app.domain.enums import Direction, Origin, Recurrence

if TYPE_CHECKING:
    from app.services.scenario_resolver import ResolvedRow


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

    @classmethod
    def from_resolved(cls, row: ResolvedRow) -> TransactionOut:
        """`row` comes from ScenarioResolver -- engine vocabulary in,
        domain vocabulary (plus real UUID/date types) out. The values are
        identical strings between app.engine.types and app.domain.enums
        by construction, so direct construction from the enum's value is
        safe and doesn't need a translation table."""
        r = row.resolved
        return cls(
            id=uuid.UUID(r.id),
            scenario_id=row.scenario_id,
            name=r.name,
            amount_minor=r.amount_minor,
            direction=Direction(r.direction.value),
            category_id=uuid.UUID(r.category_id) if r.category_id else None,
            notes=row.notes,
            recurrence=Recurrence(r.recurrence.value),
            start_date=r.start_date,
            end_date=r.end_date,
            origin=Origin(r.origin.value),
            created_at=row.created_at,
            updated_at=row.updated_at,
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


class ScenarioRefOut(BaseModel):
    id: uuid.UUID
    name: str


class DependentsOut(BaseModel):
    """Backs GET /transactions/{id}/dependents -- architecture §6.3/§9.
    `count` lets the client cheaply pick between the two C5 confirm-dialog
    variants (screen-flow §6.4); `scenarios` lets it name the affected
    plans instead of showing a bare count."""

    count: int
    scenarios: list[ScenarioRefOut]

    @classmethod
    def from_scenarios(cls, scenarios) -> DependentsOut:
        refs = [ScenarioRefOut(id=s.id, name=s.name) for s in scenarios]
        return cls(count=len(refs), scenarios=refs)


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
