"""Runs the forecast twice and hands both ledgers to the engine's
compare(). Rejects comparing a scenario with itself before either
forecast even runs -- the check that's cheap to do first."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.engine.compare import compare as engine_compare
from app.engine.models import Comparison
from app.engine.types import YearMonth
from app.services.forecast_service import ForecastResult, ForecastService


@dataclass(frozen=True)
class CompareResult:
    a: ForecastResult
    b: ForecastResult
    comparison: Comparison


class CompareService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.forecasts = ForecastService(db)

    def compare(
        self,
        user_id: uuid.UUID,
        scenario_a_id: uuid.UUID,
        scenario_b_id: uuid.UUID,
        *,
        horizon_months: int,
        anchor_month: YearMonth,
    ) -> CompareResult:
        if scenario_a_id == scenario_b_id:
            raise APIError("compare.same_scenario")

        # Same explicit anchor_month passed into both -- never let either
        # call independently default to "now", or a request straddling a
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
