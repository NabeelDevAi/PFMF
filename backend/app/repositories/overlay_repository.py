from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

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
