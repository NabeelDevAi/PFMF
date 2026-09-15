from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.scenario import Scenario


class ScenarioRepository:
    """All SQL for scenarios. Base protection (cannot delete/archive,
    cannot create a second one) is a service-layer rule, not enforced
    here -- this repository will do whatever it's asked, per
    backend-plan/05-repositories-module.md §3."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create_base(self, *, user_id: uuid.UUID, name: str = "Base Plan") -> Scenario:
        scenario = Scenario(user_id=user_id, name=name, is_base=True)
        self.db.add(scenario)
        self.db.flush()
        return scenario

    def create(
        self, *, user_id: uuid.UUID, name: str, current_balance_override_minor: int | None = None
    ) -> Scenario:
        scenario = Scenario(
            user_id=user_id,
            name=name,
            is_base=False,
            current_balance_override_minor=current_balance_override_minor,
        )
        self.db.add(scenario)
        self.db.flush()
        return scenario

    def get_by_id(self, user_id: uuid.UUID, scenario_id: uuid.UUID) -> Scenario | None:
        return self.db.scalar(
            select(Scenario).where(Scenario.id == scenario_id, Scenario.user_id == user_id)
        )

    def get_base(self, user_id: uuid.UUID) -> Scenario | None:
        return self.db.scalar(
            select(Scenario).where(Scenario.user_id == user_id, Scenario.is_base.is_(True))
        )

    def get_by_name(self, user_id: uuid.UUID, name: str) -> Scenario | None:
        return self.db.scalar(
            select(Scenario).where(Scenario.user_id == user_id, Scenario.name == name)
        )

    def list_for_user(
        self, user_id: uuid.UUID, *, include_archived: bool = False
    ) -> list[Scenario]:
        stmt = select(Scenario).where(Scenario.user_id == user_id)
        if not include_archived:
            stmt = stmt.where(Scenario.archived_at.is_(None))
        # Base first, then most recently created.
        stmt = stmt.order_by(Scenario.is_base.desc(), Scenario.created_at)
        return list(self.db.scalars(stmt))

    def count_for_user(self, user_id: uuid.UUID) -> int:
        """Excludes archived scenarios (architecture §6.2: "archived
        scenarios do not count toward any scenario cap") -- archiving is
        meant to actually declutter an account against the cap, not just
        the switcher/list. Used by ScenarioService for the
        scenario.limit_reached check."""
        return self.db.scalar(
            select(func.count())
            .select_from(Scenario)
            .where(Scenario.user_id == user_id, Scenario.archived_at.is_(None))
        )

    def save(self, scenario: Scenario) -> None:
        self.db.flush()

    def archive(self, scenario: Scenario) -> None:
        scenario.archived_at = datetime.now(UTC)
        self.db.flush()

    def unarchive(self, scenario: Scenario) -> None:
        scenario.archived_at = None
        self.db.flush()

    def delete(self, scenario: Scenario) -> None:
        self.db.delete(scenario)
        self.db.flush()

    def delete_all_non_base_for_user(self, user_id: uuid.UUID) -> None:
        """Bulk delete every derived scenario -- used by account reset.
        Cascades (ON DELETE CASCADE) take care of their transactions and
        overlays. Base itself is never touched here, matching the same
        immutability rule enforced everywhere else in the service layer."""
        self.db.execute(
            sa_delete(Scenario).where(Scenario.user_id == user_id, Scenario.is_base.is_(False))
        )
        self.db.flush()
