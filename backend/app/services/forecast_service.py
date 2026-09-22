"""Load -> resolve -> engine -> result. This is the one service that
actually calls the engine (backend-plan/06). The engine never reads a
clock; this service is the one place that does, for two things only
(architecture §7.1): defaulting a missing anchor to `balance_as_of`, and
computing `current_month`/`months_elapsed` so the client never derives
either from its own device clock. `anchor_month` stays an explicit,
optional argument all the way down to the engine -- passing one
reproduces any forecast exactly, for QA, a bug report, or the client's
own test cases.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import APIError
from app.db.models.scenario import Scenario
from app.engine.forecast import forecast as engine_forecast
from app.engine.models import Ledger
from app.engine.types import YearMonth
from app.repositories.scenario_repository import ScenarioRepository
from app.services.scenario_resolver import ScenarioResolver
from app.services.settings_service import SettingsService


@dataclass(frozen=True)
class ForecastResult:
    scenario_id: uuid.UUID
    currency_code: str
    balance_as_of: date
    current_month: YearMonth
    months_elapsed: int
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
        anchor_month: YearMonth | None = None,
    ) -> ForecastResult:
        # architecture §11.4: the four client-facing presets (12/36/60/120)
        # are no longer the whole allowed set -- the dashboard requests
        # months_elapsed + 12, which usually isn't one of them. Range only.
        max_horizon = get_settings().max_horizon_months
        if not 1 <= horizon_months <= max_horizon:
            raise APIError("forecast.invalid_horizon")

        scenario = self._get_scenario(user_id, scenario_id)
        settings = self.settings.get(user_id)
        # Scenario's own override wins; NULL means inherit from user_settings
        # (architecture §5) -- the same rule Base itself follows, since Base
        # is just a scenario with is_base=true, no special-cased Current
        # Cash Balance logic of its own.
        current_balance_minor = (
            scenario.current_balance_override_minor
            if scenario.current_balance_override_minor is not None
            else settings.current_balance_minor
        )

        # The anchor is the as-of month, which may be in the past -- an
        # explicit ?anchor= always wins (reproducibility); omitted, it
        # defaults to balance_as_of, never to today (architecture §7.1,
        # build spec §11.4). balance_as_of is user-level (D-14), so this
        # default is identical for every scenario under this user,
        # including both sides of a compare.
        resolved_anchor = (
            anchor_month
            if anchor_month is not None
            else YearMonth.from_date(settings.balance_as_of)
        )
        # The one place this service reads a clock, for exactly the two
        # things architecture §7.1 permits outside the engine: where
        # "today" sits in the returned rows, and (client-side) whether to
        # show the stale-balance prompt.
        current_month = YearMonth.from_date(date.today())
        months_elapsed = resolved_anchor.months_until(current_month)

        resolved = self.resolver.resolve(user_id, scenario)
        ledger = engine_forecast(
            current_balance_minor=current_balance_minor,
            anchor_month=resolved_anchor,
            horizon_months=horizon_months,
            transactions=resolved,
        )
        return ForecastResult(
            scenario_id=scenario.id,
            currency_code=settings.currency_code,
            balance_as_of=settings.balance_as_of,
            current_month=current_month,
            months_elapsed=months_elapsed,
            ledger=ledger,
        )

    def _get_scenario(self, user_id: uuid.UUID, scenario_id: uuid.UUID) -> Scenario:
        scenario = self.scenarios.get_by_id(user_id, scenario_id)
        if scenario is None:
            raise APIError("resource.not_found")
        return scenario
