"""Transaction CRUD, scoped to the scenario a caller owns directly.

Milestone scoping (see backend-plan/11 M3 vs M4): a scenario's
"transactions view" here is just its own raw rows -- no overlay
resolution, since scenario_overlays doesn't exist until M4. A derived
scenario in this milestone shows only what's been added directly to it,
never Base's inherited rows. See Origin's docstring in app.domain.enums.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.api.errors import APIError
from app.core.config import get_settings
from app.db.models.transaction import Transaction
from app.domain.enums import Direction, Origin, Recurrence
from app.repositories.category_repository import CategoryRepository
from app.repositories.scenario_repository import ScenarioRepository
from app.repositories.transaction_repository import TransactionRepository


class TransactionService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.transactions = TransactionRepository(db)
        self.scenarios = ScenarioRepository(db)
        self.categories = CategoryRepository(db)

    def list_for_scenario(
        self, user_id: uuid.UUID, scenario_id: uuid.UUID
    ) -> list[tuple[Transaction, Origin]]:
        scenario = self._get_scenario(user_id, scenario_id)
        origin = Origin.OWN if scenario.is_base else Origin.ADDED
        return [(txn, origin) for txn in self.transactions.list_by_scenario(user_id, scenario_id)]

    def get(self, user_id: uuid.UUID, transaction_id: uuid.UUID) -> Transaction:
        txn = self.transactions.get_by_id(user_id, transaction_id)
        if txn is None:
            raise APIError("resource.not_found")
        return txn

    def create(
        self,
        user_id: uuid.UUID,
        scenario_id: uuid.UUID,
        *,
        name: str,
        amount_minor: int,
        direction: Direction,
        recurrence: Recurrence,
        start_date: date,
        end_date: date | None = None,
        category_id: uuid.UUID | None = None,
        notes: str | None = None,
    ) -> Transaction:
        self._get_scenario(user_id, scenario_id)
        self._check_scenario_capacity(user_id, scenario_id)
        self._check_amount(amount_minor)
        self._check_dates(recurrence, start_date, end_date)
        self._check_category(user_id, category_id)

        return self.transactions.create(
            user_id=user_id,
            scenario_id=scenario_id,
            name=name,
            amount_minor=amount_minor,
            direction=direction,
            recurrence=recurrence,
            start_date=start_date,
            end_date=end_date,
            category_id=category_id,
            notes=notes,
        )

    def update(
        self,
        user_id: uuid.UUID,
        transaction_id: uuid.UUID,
        *,
        name: str | None = None,
        amount_minor: int | None = None,
        direction: Direction | None = None,
        recurrence: Recurrence | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        _unset_end_date: bool = False,
        category_id: uuid.UUID | None = None,
        _unset_category_id: bool = False,
        notes: str | None = None,
        _unset_notes: bool = False,
    ) -> Transaction:
        txn = self.get(user_id, transaction_id)

        if direction is not None and direction != txn.direction:
            raise APIError("transaction.direction_immutable")

        new_amount = amount_minor if amount_minor is not None else txn.amount_minor
        new_recurrence = recurrence if recurrence is not None else txn.recurrence
        new_start = start_date if start_date is not None else txn.start_date
        new_end = txn.end_date if not _unset_end_date else None
        new_end = end_date if end_date is not None else new_end

        self._check_amount(new_amount)
        self._check_dates(new_recurrence, new_start, new_end)
        if not _unset_category_id and category_id is not None:
            self._check_category(user_id, category_id)

        txn.name = name if name is not None else txn.name
        txn.amount_minor = new_amount
        txn.recurrence = new_recurrence
        txn.start_date = new_start
        txn.end_date = new_end
        if _unset_category_id:
            txn.category_id = None
        elif category_id is not None:
            txn.category_id = category_id
        if _unset_notes:
            txn.notes = None
        elif notes is not None:
            txn.notes = notes

        self.transactions.save(txn)
        return txn

    def delete(self, user_id: uuid.UUID, transaction_id: uuid.UUID) -> None:
        txn = self.get(user_id, transaction_id)
        self.transactions.delete(txn)

    def _get_scenario(self, user_id: uuid.UUID, scenario_id: uuid.UUID):
        scenario = self.scenarios.get_by_id(user_id, scenario_id)
        if scenario is None:
            raise APIError("resource.not_found")
        return scenario

    def _check_scenario_capacity(self, user_id: uuid.UUID, scenario_id: uuid.UUID) -> None:
        settings = get_settings()
        if (
            self.transactions.count_for_scenario(user_id, scenario_id)
            >= settings.max_transactions_per_scenario
        ):
            raise APIError("transaction.limit_reached")

    def _check_amount(self, amount_minor: int) -> None:
        if amount_minor <= 0:
            raise APIError("transaction.amount_not_positive", {"field": "amount_minor"})

    def _check_dates(self, recurrence: Recurrence, start_date: date, end_date: date | None) -> None:
        if end_date is not None and end_date < start_date:
            raise APIError("transaction.end_before_start", {"field": "end_date"})
        if recurrence is Recurrence.ONE_TIME and end_date is not None:
            raise APIError("transaction.one_time_has_end_date", {"field": "end_date"})

    def _check_category(self, user_id: uuid.UUID, category_id: uuid.UUID | None) -> None:
        if (
            category_id is not None
            and self.categories.get_visible_to_user(user_id, category_id) is None
        ):
            raise APIError("validation.invalid", {"field": "category_id"})
