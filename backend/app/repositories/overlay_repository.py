from __future__ import annotations

import uuid

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.db.models.scenario import Scenario
from app.db.models.scenario_overlay import ScenarioOverlay


class OverlayRepository:
    """Scoped by scenario_id, not user_id -- scenario_overlays has no
    user_id column (see the migration's docstring). Callers (services)
    must ownership-check the scenario itself first, via ScenarioRepository."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_by_scenario(self, scenario_id: uuid.UUID) -> list[ScenarioOverlay]:
        return list(
            self.db.scalars(
                select(ScenarioOverlay).where(ScenarioOverlay.scenario_id == scenario_id)
            )
        )

    def list_all_for_user(self, user_id: uuid.UUID) -> list[ScenarioOverlay]:
        """Every overlay across every scenario this user owns -- for
        GET /me/export. The only overlay query that needs a join, since
        there's no user_id column here to filter on directly."""
        stmt = (
            select(ScenarioOverlay)
            .join(Scenario, ScenarioOverlay.scenario_id == Scenario.id)
            .where(Scenario.user_id == user_id)
            .order_by(ScenarioOverlay.scenario_id, ScenarioOverlay.created_at)
        )
        return list(self.db.scalars(stmt))

    def exists_with_category_for_user(self, user_id: uuid.UUID, category_id: uuid.UUID) -> bool:
        """Same purpose as TransactionRepository.exists_with_category: an
        ovr_category_id also has no ON DELETE rule against categories.
        No user_id column here, so the join through Scenario (same as
        list_all_for_user) is what scopes this to the caller."""
        stmt = select(
            exists().where(
                ScenarioOverlay.ovr_category_id == category_id,
                ScenarioOverlay.scenario_id == Scenario.id,
                Scenario.user_id == user_id,
            )
        )
        return bool(self.db.scalar(stmt))

    def get_by_id(self, scenario_id: uuid.UUID, overlay_id: uuid.UUID) -> ScenarioOverlay | None:
        return self.db.scalar(
            select(ScenarioOverlay).where(
                ScenarioOverlay.id == overlay_id, ScenarioOverlay.scenario_id == scenario_id
            )
        )

    def get_by_target(
        self, scenario_id: uuid.UUID, base_transaction_id: uuid.UUID
    ) -> ScenarioOverlay | None:
        return self.db.scalar(
            select(ScenarioOverlay).where(
                ScenarioOverlay.scenario_id == scenario_id,
                ScenarioOverlay.base_transaction_id == base_transaction_id,
            )
        )

    def create(
        self, *, scenario_id: uuid.UUID, base_transaction_id: uuid.UUID, **fields
    ) -> ScenarioOverlay:
        overlay = ScenarioOverlay(
            scenario_id=scenario_id, base_transaction_id=base_transaction_id, **fields
        )
        self.db.add(overlay)
        self.db.flush()
        return overlay

    def save(self, overlay: ScenarioOverlay) -> None:
        self.db.flush()

    def delete(self, overlay: ScenarioOverlay) -> None:
        self.db.delete(overlay)
        self.db.flush()
