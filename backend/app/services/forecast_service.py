"""Load -> resolve -> engine -> result. This is the one service that
actually calls the engine (backend-plan/06). The engine never reads a
clock; this service doesn't either -- `anchor_month` is a required,
explicit argument here, resolved from "now" one layer up, in the API
router (architecture: "anchor is optional... resolved in the API layer,
not the engine"). Accepting an explicit anchor at every layer down to
the engine is what lets any forecast be reproduced exactly, for QA, a
bug report, or the client's own test cases.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.db.models.scenario import Scenario
from app.engine.forecast import forecast as engine_forecast
from app.engine.models import Ledger
from app.engine.types import YearMonth
from app.repositories.scenario_repository import ScenarioRepository
from app.services.scenario_resolver import ScenarioResolver
from app.services.settings_service import SettingsService

# architecture §11.4 / backend-plan §08: exactly these four, not a range.
ALLOWED_HORIZONS = (12, 36, 60, 120)


@dataclass(frozen=True)
class ForecastResult:
    scenario_id: uuid.UUID
    currency_code: str
    ledger: Ledger


class ForecastService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.scenarios = ScenarioRepository(db)
        self.settings = SettingsService(db)
        self.resolver = ScenarioResolver(db)

    def forecast(
        self,
        user_id: uuid.UUID,
        scenario_id: uuid.UUID,
        *,
        horizon_months: int,
        anchor_month: YearMonth,
    ) -> ForecastResult:
        if horizon_months not in ALLOWED_HORIZONS:
            raise APIError("forecast.invalid_horizon")

        scenario = self._get_scenario(user_id, scenario_id)
        settings = self.settings.get(user_id)
        # Scenario's own override wins; NULL means inherit from user_settings
        # (architecture §5) -- the same rule Base itself follows, since Base
        # is just a scenario with is_base=true, no special-cased opening
        # balance logic of its own.
        opening_balance_minor = (
            scenario.opening_balance_override_minor
            if scenario.opening_balance_override_minor is not None
            else settings.opening_balance_minor
        )

        resolved = self.resolver.resolve(user_id, scenario)
        ledger = engine_forecast(
            opening_balance_minor=opening_balance_minor,
            anchor_month=anchor_month,
            horizon_months=horizon_months,
            transactions=resolved,
        )
        return ForecastResult(
            scenario_id=scenario.id, currency_code=settings.currency_code, ledger=ledger
        )

    def _get_scenario(self, user_id: uuid.UUID, scenario_id: uuid.UUID) -> Scenario:
        scenario = self.scenarios.get_by_id(user_id, scenario_id)
        if scenario is None:
            raise APIError("resource.not_found")
        return scenario
