"""Turns a scenario into the flat list of resolved transactions the pure
engine consumes. Implements architecture §6's resolution algorithm
exactly. This is the bridge between messy, mutable persistence and the
engine's pure world -- the one service backend-plan/06 calls out for the
heaviest test coverage in the backend, because every bug that could ever
leak into a user's real Base plan would leak in here.

Two queries per non-base resolution, never N+1: one for Base's own
transactions, one for this scenario's overlays (indexed in memory by
base_transaction_id), plus one for this scenario's own local additions.
Base itself needs only its own transactions -- one query.

Never mutates an ORM row to represent an override: a patched view is
built as a plain dict of field values (see _base_fields/_patched_fields),
so an override can never accidentally get flushed onto Base's real
transaction. That would be exactly the isolation guarantee failing.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.db.models.scenario import Scenario
from app.db.models.scenario_overlay import ScenarioOverlay
from app.db.models.transaction import Transaction
from app.domain.enums import Direction, OverlayOp, Recurrence
from app.engine.models import ResolvedTransaction
from app.engine.types import Direction as EngineDirection
from app.engine.types import Origin as EngineOrigin
from app.engine.types import Recurrence as EngineRecurrence
from app.repositories.overlay_repository import OverlayRepository
from app.repositories.scenario_repository import ScenarioRepository
from app.repositories.transaction_repository import TransactionRepository


@dataclass(frozen=True)
class ResolvedRow:
    """`resolve()`'s engine-ready output plus what the API list endpoint
    needs but the engine has no use for: `scenario_id` is the scenario
    being *viewed* (not necessarily where the row physically lives --
    an inherited row's scenario_id is the derived scenario, not Base),
    `notes` (there's no ovr_notes column, so it's never overridable and
    always comes straight from the underlying transaction), the audit
    timestamps, and `overlay_id` -- the overlay's own id for an OVERRIDDEN
    row (None for OWN/INHERITED/ADDED, which have no overlay at all). The
    client needs this to call PATCH/DELETE .../overlays/{overlay_id} on a
    row it's already looking at, rather than having to remember an id it
    only ever saw once, back when the overlay was first created.
    INHERITED and OVERRIDDEN rows carry Base's own created_at/updated_at
    -- the overlay isn't a second, independently tracked lifecycle at
    this granularity (scenario_overlays has no updated_at column, by
    design)."""

    resolved: ResolvedTransaction
    scenario_id: uuid.UUID
    notes: str | None
    created_at: datetime
    updated_at: datetime
    overlay_id: uuid.UUID | None = None


@dataclass(frozen=True)
class ExcludedRow:
    """A Base transaction currently excluded ("removed") from a derived
    scenario. Deliberately not a ResolvedRow/ResolvedTransaction -- an
    excluded row doesn't exist in the resolved ledger at all and is never
    fed to the engine, so it needs no engine-vocabulary translation, just
    Base's own field values verbatim (an exclude overlay carries no
    ovr_* fields to apply, unlike an override). `overlay_id` is what the
    client calls DELETE .../overlays/{overlay_id} on to restore it."""

    id: uuid.UUID
    overlay_id: uuid.UUID
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


class ScenarioResolver:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.scenarios = ScenarioRepository(db)
        self.transactions = TransactionRepository(db)
        self.overlays = OverlayRepository(db)

    def resolve(self, user_id: uuid.UUID, scenario: Scenario) -> list[ResolvedTransaction]:
        return [row.resolved for row in self._resolve_rows(user_id, scenario)]

    def resolve_for_api(self, user_id: uuid.UUID, scenario: Scenario) -> list[ResolvedRow]:
        return self._resolve_rows(user_id, scenario)

    def resolve_excluded_for_api(self, user_id: uuid.UUID, scenario: Scenario) -> list[ExcludedRow]:
        """The "removed from this plan" rows -- deliberately a separate
        method from _resolve_rows (not a flag on it) so that function,
        the single most sensitive one in the backend, stays exactly as
        it was: this never touches what the engine sees. Base can't
        exclude anything (exclusion is a derived-scenario-only concept),
        so it always returns empty here."""
        if scenario.is_base:
            return []

        base = self.scenarios.get_base(user_id)
        base_rows = self.transactions.list_by_scenario(user_id, base.id) if base else []
        overlays_by_target = {
            ov.base_transaction_id: ov for ov in self.overlays.list_by_scenario(scenario.id)
        }

        out: list[ExcludedRow] = []
        for txn in base_rows:
            ov = overlays_by_target.get(txn.id)
            if ov is not None and ov.op is OverlayOp.EXCLUDE:
                out.append(_excluded_row(txn, ov, scenario.id))
        return out

    def _resolve_rows(self, user_id: uuid.UUID, scenario: Scenario) -> list[ResolvedRow]:
        if scenario.is_base:
            own = self.transactions.list_by_scenario(user_id, scenario.id)
            return [_row(t, _base_fields(t), EngineOrigin.OWN, scenario.id) for t in own]

        base = self.scenarios.get_base(user_id)
        base_rows = self.transactions.list_by_scenario(user_id, base.id) if base else []
        overlays_by_target = {
            ov.base_transaction_id: ov for ov in self.overlays.list_by_scenario(scenario.id)
        }

        out: list[ResolvedRow] = []
        for txn in base_rows:
            ov = overlays_by_target.get(txn.id)
            if ov is None:
                out.append(_row(txn, _base_fields(txn), EngineOrigin.INHERITED, scenario.id))
            elif ov.op is OverlayOp.EXCLUDE:
                continue
            else:  # OVERRIDE
                out.append(
                    _row(
                        txn,
                        _patched_fields(txn, ov),
                        EngineOrigin.OVERRIDDEN,
                        scenario.id,
                        overlay_id=ov.id,
                    )
                )

        for txn in self.transactions.list_by_scenario(user_id, scenario.id):
            out.append(_row(txn, _base_fields(txn), EngineOrigin.ADDED, scenario.id))

        return out


def _base_fields(txn: Transaction) -> dict:
    return {
        "name": txn.name,
        "amount_minor": txn.amount_minor,
        "direction": txn.direction,
        "category_id": txn.category_id,
        "recurrence": txn.recurrence,
        "start_date": txn.start_date,
        "end_date": txn.end_date,
    }


def _patched_fields(txn: Transaction, ov: ScenarioOverlay) -> dict:
    """Each ovr_* field is used when non-NULL, otherwise the Base value.
    Direction is never overridden -- there's no ovr_direction column.
    `unset_end_date` forces end_date to NULL regardless of Base's value."""
    fields = _base_fields(txn)
    if ov.ovr_name is not None:
        fields["name"] = ov.ovr_name
    if ov.ovr_amount_minor is not None:
        fields["amount_minor"] = ov.ovr_amount_minor
    if ov.ovr_category_id is not None:
        fields["category_id"] = ov.ovr_category_id
    if ov.ovr_recurrence is not None:
        fields["recurrence"] = ov.ovr_recurrence
    if ov.ovr_start_date is not None:
        fields["start_date"] = ov.ovr_start_date
    if ov.unset_end_date:
        fields["end_date"] = None
    elif ov.ovr_end_date is not None:
        fields["end_date"] = ov.ovr_end_date
    return fields


def _row(
    txn: Transaction,
    fields: dict,
    origin: EngineOrigin,
    scenario_id: uuid.UUID,
    *,
    overlay_id: uuid.UUID | None = None,
) -> ResolvedRow:
    resolved = ResolvedTransaction(
        id=str(txn.id),
        source_id=str(txn.id),
        origin=origin,
        name=fields["name"],
        amount_minor=fields["amount_minor"],
        direction=EngineDirection(fields["direction"].value),
        category_id=str(fields["category_id"]) if fields["category_id"] else None,
        recurrence=EngineRecurrence(fields["recurrence"].value),
        start_date=fields["start_date"],
        end_date=fields["end_date"],
    )
    return ResolvedRow(
        resolved=resolved,
        scenario_id=scenario_id,
        notes=txn.notes,
        created_at=txn.created_at,
        updated_at=txn.updated_at,
        overlay_id=overlay_id,
    )


def _excluded_row(txn: Transaction, ov: ScenarioOverlay, scenario_id: uuid.UUID) -> ExcludedRow:
    """Always Base's own field values verbatim -- an exclude overlay has
    no ovr_* fields at all, unlike an override."""
    return ExcludedRow(
        id=txn.id,
        overlay_id=ov.id,
        scenario_id=scenario_id,
        name=txn.name,
        amount_minor=txn.amount_minor,
        direction=txn.direction,
        category_id=txn.category_id,
        notes=txn.notes,
        recurrence=txn.recurrence,
        start_date=txn.start_date,
        end_date=txn.end_date,
        created_at=txn.created_at,
        updated_at=txn.updated_at,
    )
