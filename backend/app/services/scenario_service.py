"""Scenario CRUD, Base protection, duplicate, archive/unarchive.

Duplicate copies only the source's own transactions in this milestone --
scenario_overlays doesn't exist until M4, so there's nothing else to copy
yet. Architecture §5.1: duplicating never creates a parent link; the copy
is always a plain, non-base scenario regardless of what was duplicated.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import APIError
from app.db.models.scenario import Scenario
from app.repositories.scenario_repository import ScenarioRepository
from app.repositories.transaction_repository import TransactionRepository


class ScenarioService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.scenarios = ScenarioRepository(db)
        self.transactions = TransactionRepository(db)

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
        self.scenarios.unarchive(scenario)
        return scenario

    def duplicate(
        self, user_id: uuid.UUID, scenario_id: uuid.UUID, *, name: str | None = None
    ) -> Scenario:
        source = self.get(user_id, scenario_id)
        self._check_capacity(user_id)
        new_name = name or f"{source.name} (copy)"
        self._check_name_available(user_id, new_name)

        copy = self.scenarios.create(user_id=user_id, name=new_name)
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
