"""Import every ORM model here so Base.metadata is complete as soon as
anything imports app.db.models -- this is what alembic/env.py relies on for
autogenerate, and what tests/conftest.py relies on to create the schema."""

from app.db.models.category import Category
from app.db.models.password_reset_token import PasswordResetToken
from app.db.models.refresh_token import RefreshToken
from app.db.models.scenario import Scenario
from app.db.models.user import User
from app.db.models.user_settings import UserSettings

__all__ = [
    "Category",
    "PasswordResetToken",
    "RefreshToken",
    "Scenario",
    "User",
    "UserSettings",
]
