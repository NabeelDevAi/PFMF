"""Scenario CRUD, Base protection, duplicate, archive/unarchive.

Duplicate copies a derived source's own overlays and own transactions,
with fresh ids and an independent live link back to Base (D-13, M1 case
25.15). A Base source copies nothing at all -- inheritance alone
reproduces it (M1 case 25.16); copying Base's own rows would double
every item. Architecture §5.1: duplicating never creates a parent link;
the copy is always a plain, non-base scenario regardless of what was
duplicated.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import APIError
from app.db.models.scenario import Scenario
from app.repositories.overlay_repository import OverlayRepository
from app.repositories.scenario_repository import ScenarioRepository
from app.repositories.transaction_repository import TransactionRepository


class ScenarioService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.scenarios = ScenarioRepository(db)
        self.transactions = TransactionRepository(db)
        self.overlays = OverlayRepository(db)

    def list_for_user(
        self, user_id: uuid.UUID, *, include_archived: bool = False
    ) -> list[Scenario]:
        return self.scenarios.list_for_user(user_id, include_archived=include_archived)

    def get(self, user_id: uuid.UUID, scenario_id: uuid.UUID) -> Scenario:
        scenario = self.scenarios.get_by_id(user_id, scenario_id)
        if scenario is None:
            raise APIError("resource.not_found")
        return scenario

    def create(
        self, user_id: uuid.UUID, *, name: str, current_balance_override_minor: int | None = None
    ) -> Scenario:
        self._check_capacity(user_id)
        self._check_name_available(user_id, name)
        return self.scenarios.create(
            user_id=user_id,
            name=name,
            current_balance_override_minor=current_balance_override_minor,
        )

    def patch(
        self,
        user_id: uuid.UUID,
        scenario_id: uuid.UUID,
        *,
        name: str | None = None,
        current_balance_override_minor: int | None = None,
        _unset_current_balance_override: bool = False,
    ) -> Scenario:
        scenario = self.get(user_id, scenario_id)
        if name is not None and name != scenario.name:
            self._check_name_available(user_id, name)
            scenario.name = name
        if _unset_current_balance_override:
            scenario.current_balance_override_minor = None
        elif current_balance_override_minor is not None:
            scenario.current_balance_override_minor = current_balance_override_minor
        self.scenarios.save(scenario)
        return scenario

    def delete(self, user_id: uuid.UUID, scenario_id: uuid.UUID) -> None:
        scenario = self.get(user_id, scenario_id)
        if scenario.is_base:
            raise APIError("scenario.base_immutable")
        self.scenarios.delete(scenario)

    def archive(self, user_id: uuid.UUID, scenario_id: uuid.UUID) -> Scenario:
        scenario = self.get(user_id, scenario_id)
        if scenario.is_base:
            raise APIError("scenario.base_immutable")
        self.scenarios.archive(scenario)
        return scenario

    def unarchive(self, user_id: uuid.UUID, scenario_id: uuid.UUID) -> Scenario:
        scenario = self.get(user_id, scenario_id)
        if scenario.archived_at is None:
            raise APIError("scenario.not_archived")
        self.scenarios.unarchive(scenario)
        return scenario

    def duplicate(
        self, user_id: uuid.UUID, scenario_id: uuid.UUID, *, name: str | None = None
    ) -> Scenario:
        source = self.get(user_id, scenario_id)
        if source.archived_at is not None:
            # Architecture §6.2: rejected as a duplicate source -- restore
            # first (screen-flow §8.1). Checked before capacity/name so an
            # archived source never spends a slot in either check first.
            raise APIError("scenario.archived")
        self._check_capacity(user_id)
        new_name = name or f"{source.name} (copy)"
        self._check_name_available(user_id, new_name)

        copy = self.scenarios.create(user_id=user_id, name=new_name)
        if not source.is_base:
            # Base source: copy nothing here at all -- see this module's
            # docstring and M1 case 25.16. Only a derived source has
            # overlays or own transactions worth copying in the first
            # place, and both need copying together or the duplicate
            # would silently lose whatever the source overrode/excluded.
            self.overlays.copy_all(from_scenario_id=source.id, to_scenario_id=copy.id)
            for txn in self.transactions.list_by_scenario(user_id, source.id):
                self.transactions.create(
                    user_id=user_id,
                    scenario_id=copy.id,
                    name=txn.name,
                    amount_minor=txn.amount_minor,
                    direction=txn.direction,
                    category_id=txn.category_id,
                    notes=txn.notes,
                    recurrence=txn.recurrence,
                    start_date=txn.start_date,
                    end_date=txn.end_date,
                )
        return copy

    def _check_name_available(self, user_id: uuid.UUID, name: str) -> None:
        if self.scenarios.get_by_name(user_id, name) is not None:
            raise APIError("scenario.name_taken", {"field": "name"})

    def _check_capacity(self, user_id: uuid.UUID) -> None:
        # 50 plans per account (product decision, not derived from either
        # locked doc -- both left the threshold as an open discovery
        # question). Counts archived scenarios too; only Base is exempt,
        # since it's created once at registration and this check never
        # runs for it.
        settings = get_settings()
        if self.scenarios.count_for_user(user_id) >= settings.max_scenarios_per_user:
            raise APIError("scenario.limit_reached")
