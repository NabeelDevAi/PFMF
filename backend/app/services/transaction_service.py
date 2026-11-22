"""Transaction CRUD, scoped to the scenario a caller owns directly.

Listing a scenario's *resolved* transactions (the view that includes
inherited/overridden Base rows) is ScenarioResolver's job, not this
service's -- see app/api/v1/transactions.py's module docstring for the
routing split this implies.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.db.models.scenario import Scenario
from app.db.models.transaction import Transaction
from app.domain.enums import Direction, Recurrence, RecurrenceUnit
from app.repositories.category_repository import CategoryRepository
from app.repositories.overlay_repository import OverlayRepository
from app.repositories.scenario_repository import ScenarioRepository
from app.repositories.transaction_repository import TransactionRepository
from app.services.recurrence_rules import check_dates, check_recurrence


class TransactionService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.transactions = TransactionRepository(db)
        self.scenarios = ScenarioRepository(db)
        self.categories = CategoryRepository(db)
        self.overlays = OverlayRepository(db)

    def get(self, user_id: uuid.UUID, transaction_id: uuid.UUID) -> Transaction:
        txn = self.transactions.get_by_id(user_id, transaction_id)
        if txn is None:
            raise APIError("resource.not_found")
        return txn

    def dependents(self, user_id: uuid.UUID, transaction_id: uuid.UUID) -> list[Scenario]:
        """Scenarios holding an overlay on this transaction (architecture
        §6.3/§9, build spec §10.4) -- lets the client warn before deleting
        a Base row. Ownership-checked the same way every other route
        here is; a non-Base transaction simply has no overlays pointing
        at it (overlays only ever target Base rows), so this returns an
        empty list for one rather than needing a special case."""
        self.get(user_id, transaction_id)
        return self.overlays.scenarios_referencing(transaction_id, user_id)

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
        recurrence_interval: int | None = None,
        recurrence_unit: RecurrenceUnit | None = None,
    ) -> Transaction:
        self._get_scenario(user_id, scenario_id)
        self._check_amount(amount_minor)
        self._check_dates(recurrence, start_date, end_date)
        self._check_category(user_id, category_id)
        recurrence_interval, recurrence_unit = check_recurrence(
            recurrence, recurrence_interval, recurrence_unit
        )

        return self.transactions.create(
            user_id=user_id,
            scenario_id=scenario_id,
            name=name,
            amount_minor=amount_minor,
            direction=direction,
            recurrence=recurrence,
            recurrence_interval=recurrence_interval,
            recurrence_unit=recurrence_unit,
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
        recurrence_interval: int | None = None,
        recurrence_unit: RecurrenceUnit | None = None,
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
        # Interval and unit belong to the recurrence: when it stays `custom`
        # an omitted field keeps its current value; switching to custom needs
        # both in the request; switching away from custom clears them (and
        # sending them with a named rule is an error).
        if new_recurrence is Recurrence.CUSTOM:
            was_custom = txn.recurrence is Recurrence.CUSTOM
            new_interval = (
                recurrence_interval
                if recurrence_interval is not None
                else (txn.recurrence_interval if was_custom else None)
            )
            new_unit = (
                recurrence_unit
                if recurrence_unit is not None
                else (txn.recurrence_unit if was_custom else None)
            )
        else:
            new_interval, new_unit = recurrence_interval, recurrence_unit
        new_interval, new_unit = check_recurrence(new_recurrence, new_interval, new_unit)
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
        txn.recurrence_interval = new_interval
        txn.recurrence_unit = new_unit
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

    def _check_amount(self, amount_minor: int) -> None:
        if amount_minor <= 0:
            raise APIError("transaction.amount_not_positive", {"field": "amount_minor"})

    def _check_dates(self, recurrence: Recurrence, start_date: date, end_date: date | None) -> None:
        check_dates(recurrence, start_date, end_date)

    def _check_category(self, user_id: uuid.UUID, category_id: uuid.UUID | None) -> None:
        if (
            category_id is not None
            and self.categories.get_visible_to_user(user_id, category_id) is None
        ):
            raise APIError("validation.invalid", {"field": "category_id"})
