"""Runs the forecast twice and hands both ledgers to the engine's
compare(). Rejects comparing a scenario with itself, and either operand
being archived, before either forecast even runs -- the checks that are
cheap to do first."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.engine.compare import compare as engine_compare
from app.engine.models import Comparison
from app.engine.types import YearMonth
from app.services.forecast_service import ForecastResult, ForecastService
from app.services.scenario_service import ScenarioService


@dataclass(frozen=True)
class CompareResult:
    a: ForecastResult
    b: ForecastResult
    comparison: Comparison


class CompareService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.forecasts = ForecastService(db)
        self.scenarios = ScenarioService(db)

    def compare(
        self,
        user_id: uuid.UUID,
        scenario_a_id: uuid.UUID,
        scenario_b_id: uuid.UUID,
        *,
        horizon_months: int,
        anchor_month: YearMonth | None = None,
    ) -> CompareResult:
        if scenario_a_id == scenario_b_id:
            raise APIError("compare.same_scenario")
        self._check_not_archived(user_id, scenario_a_id)
        self._check_not_archived(user_id, scenario_b_id)

        # Same anchor_month passed into both -- if omitted, each call
        # defaults independently, but the default (balance_as_of) is
        # user-level, not per-scenario (D-14), so both sides land on the
        # identical month regardless. Never let either side default from
        # a clock read at two different instants: a request straddling a
        # month boundary could hand the engine two ledgers it isn't
        # allowed to compare (it asserts on this itself).
        a = self.forecasts.forecast(
            user_id, scenario_a_id, horizon_months=horizon_months, anchor_month=anchor_month
        )
        b = self.forecasts.forecast(
            user_id, scenario_b_id, horizon_months=horizon_months, anchor_month=anchor_month
        )
        comparison = engine_compare(a.ledger, b.ledger)
        return CompareResult(a=a, b=b, comparison=comparison)

    def _check_not_archived(self, user_id: uuid.UUID, scenario_id: uuid.UUID) -> None:
        # Architecture §6.2: rejected as a comparison operand. Also
        # ownership-checks (resource.not_found), the same as
        # ForecastService.forecast() would do a moment later -- this just
        # fails on the archived check first, before either forecast runs.
        scenario = self.scenarios.get(user_id, scenario_id)
        if scenario.archived_at is not None:
            raise APIError("scenario.archived")
