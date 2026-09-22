"""Shared helpers for engine tests: building ResolvedTransaction objects
from plain dicts, and constructing simple transaction sets for hand-picked
invariant checks.
"""

from __future__ import annotations

from datetime import date

from app.engine.models import ResolvedTransaction
from app.engine.types import Direction, Origin, Recurrence


def txn(
    id: str,
    name: str,
    amount_minor: int,
    direction: str,
    recurrence: str,
    start_date: str,
    end_date: str | None = None,
    *,
    source_id: str | None = None,
    origin: Origin = Origin.OWN,
    category_id: str | None = None,
) -> ResolvedTransaction:
    """Build a ResolvedTransaction from plain values (as they'd appear in a
    fixture file). `source_id` defaults to `id` -- fine for engine-level
    tests, where origin/source_id don't affect the arithmetic, only
    comparison drivers and later, the resolver."""
    return ResolvedTransaction(
        id=id,
        source_id=source_id or id,
        origin=origin,
        name=name,
        amount_minor=amount_minor,
        direction=Direction(direction),
        category_id=category_id,
        recurrence=Recurrence(recurrence),
        start_date=date.fromisoformat(start_date),
        end_date=date.fromisoformat(end_date) if end_date else None,
    )


def txn_from_dict(d: dict) -> ResolvedTransaction:
    return txn(
        id=d["id"],
        name=d["name"],
        amount_minor=d["amount_minor"],
        direction=d["direction"],
        recurrence=d["recurrence"],
        start_date=d["start_date"],
        end_date=d.get("end_date"),
        source_id=d.get("source_id"),
        origin=Origin(d["origin"]) if "origin" in d else Origin.OWN,
    )
