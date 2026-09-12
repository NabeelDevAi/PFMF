"""Two route groups, deliberately living under different prefixes to match
the architecture doc's API surface exactly: listing/creating are nested
under the scenario (/scenarios/{id}/transactions), but editing/deleting a
transaction you already own directly is not (/transactions/{id}) --
because in a derived scenario, PATCH/DELETE on an *inherited* or
*overridden* row must go through the overlay endpoints instead
(architecture §9.2, app/api/v1/overlays.py), never these two. These
routes only ever reach a transaction the caller owns directly (Base's
own rows, or a scenario's own ADDED rows) -- TransactionService.get()
looks up by transactions.user_id, and an inherited row simply isn't a
row in that table at all.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.schemas.transactions import (
    TransactionCreate,
    TransactionListOut,
    TransactionOut,
    TransactionPatch,
)
from app.db.models.user import User
from app.db.session import get_db
from app.domain.enums import Origin
from app.services.scenario_resolver import ScenarioResolver
from app.services.scenario_service import ScenarioService
from app.services.transaction_service import TransactionService

scenario_transactions_router = APIRouter(prefix="/scenarios", tags=["transactions"])
transactions_router = APIRouter(prefix="/transactions", tags=["transactions"])


@scenario_transactions_router.get("/{scenario_id}/transactions", response_model=TransactionListOut)
def list_transactions(
    scenario_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> TransactionListOut:
    scenario = ScenarioService(db).get(user.id, scenario_id)
    rows = ScenarioResolver(db).resolve_for_api(user.id, scenario)
    return TransactionListOut(items=[TransactionOut.from_resolved(row) for row in rows])


@scenario_transactions_router.post(
    "/{scenario_id}/transactions",
    response_model=TransactionOut,
    status_code=status.HTTP_201_CREATED,
)
def create_transaction(
    scenario_id: uuid.UUID,
    body: TransactionCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TransactionOut:
    service = TransactionService(db)
    txn = service.create(
        user.id,
        scenario_id,
        name=body.name,
        amount_minor=body.amount_minor,
        direction=body.direction,
        recurrence=body.recurrence,
        start_date=body.start_date,
        end_date=body.end_date,
        category_id=body.category_id,
        notes=body.notes,
    )
    db.commit()
    # A transaction created directly on a scenario is always its own row:
    # OWN if that scenario is Base, ADDED otherwise -- never INHERITED or
    # OVERRIDDEN, which only exist in the *resolved* view (list_transactions
    # above), not as rows anyone creates directly.
    scenario = service.scenarios.get_by_id(user.id, scenario_id)
    origin = _own_or_added(scenario.is_base)
    return TransactionOut.from_row(txn, origin)


@transactions_router.patch("/{transaction_id}", response_model=TransactionOut)
def patch_transaction(
    transaction_id: uuid.UUID,
    body: TransactionPatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TransactionOut:
    service = TransactionService(db)
    txn = service.update(
        user.id,
        transaction_id,
        name=body.name,
        amount_minor=body.amount_minor,
        direction=body.direction,
        recurrence=body.recurrence,
        start_date=body.start_date,
        end_date=body.end_date,
        _unset_end_date=body.unset_end_date,
        category_id=body.category_id,
        _unset_category_id=body.unset_category_id,
        notes=body.notes,
        _unset_notes=body.unset_notes,
    )
    db.commit()
    scenario = service.scenarios.get_by_id(user.id, txn.scenario_id)
    return TransactionOut.from_row(txn, _own_or_added(scenario.is_base))


@transactions_router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(
    transaction_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> None:
    TransactionService(db).delete(user.id, transaction_id)
    db.commit()


def _own_or_added(is_base: bool) -> Origin:
    return Origin.OWN if is_base else Origin.ADDED
