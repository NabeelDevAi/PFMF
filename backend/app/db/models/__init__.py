"""Import every ORM model here so Base.metadata is complete as soon as
anything imports app.db.models -- this is what alembic/env.py relies on for
autogenerate, and what tests/conftest.py relies on to create the schema."""

from app.db.models.category import Category
from app.db.models.refresh_token import RefreshToken
from app.db.models.scenario import Scenario
from app.db.models.scenario_overlay import ScenarioOverlay
from app.db.models.transaction import Transaction
from app.db.models.user import User
from app.db.models.user_settings import UserSettings

__all__ = [
    "Category",
    "RefreshToken",
    "Scenario",
    "ScenarioOverlay",
    "Transaction",
    "User",
    "UserSettings",
]
