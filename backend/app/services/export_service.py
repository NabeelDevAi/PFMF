"""GET /me/export (RFP §4.8, architecture §9). A full, raw dump of
everything this user owns -- not a resolved/forecast view. Resolution is
just a computed lens over these same rows (ScenarioResolver), so this
export is already a complete, reconstructable backup on its own: it
includes Base's own transactions, every derived scenario's own
additions, and every overlay describing how each derived scenario
differs from Base.

System categories are deliberately excluded -- they're global reference
data, not this user's data.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.db.models.category import Category
from app.db.models.scenario import Scenario
from app.db.models.scenario_overlay import ScenarioOverlay
from app.db.models.transaction import Transaction
from app.db.models.user import User
from app.db.models.user_settings import UserSettings
from app.repositories.category_repository import CategoryRepository
from app.repositories.overlay_repository import OverlayRepository
from app.repositories.scenario_repository import ScenarioRepository
from app.repositories.transaction_repository import TransactionRepository
from app.repositories.user_repository import UserRepository
from app.repositories.user_settings_repository import UserSettingsRepository


@dataclass(frozen=True)
class ExportData:
    user: User
    settings: UserSettings
    categories: list[Category]
    scenarios: list[Scenario]
    transactions: list[Transaction]
    overlays: list[ScenarioOverlay]


class ExportService:
    def __init__(self, db: Session) -> None:
        self.users = UserRepository(db)
        self.settings = UserSettingsRepository(db)
        self.categories = CategoryRepository(db)
        self.scenarios = ScenarioRepository(db)
        self.transactions = TransactionRepository(db)
        self.overlays = OverlayRepository(db)

    def export(self, user_id: uuid.UUID) -> ExportData:
        user = self.users.get_by_id(user_id)
        settings = self.settings.get_by_user_id(user_id)
        if user is None or settings is None:
            raise APIError("resource.not_found")

        return ExportData(
            user=user,
            settings=settings,
            categories=self.categories.list_owned_by_user(user_id),
            scenarios=self.scenarios.list_for_user(user_id, include_archived=True),
            transactions=self.transactions.list_all_for_user(user_id),
            overlays=self.overlays.list_all_for_user(user_id),
        )
