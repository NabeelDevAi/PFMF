from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.scenario import Scenario


class ScenarioRepository:
    """Minimal for milestone M2: register() needs to create a user's Base
    scenario. Full CRUD (rename, duplicate, archive, delete) lands in M3 --
    see backend-plan/06-services-module.md."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create_base(self, *, user_id: uuid.UUID, name: str = "Base Plan") -> Scenario:
        scenario = Scenario(user_id=user_id, name=name, is_base=True)
        self.db.add(scenario)
        self.db.flush()
        return scenario

    def get_base(self, user_id: uuid.UUID) -> Scenario | None:
        return self.db.scalar(
            select(Scenario).where(Scenario.user_id == user_id, Scenario.is_base.is_(True))
        )
