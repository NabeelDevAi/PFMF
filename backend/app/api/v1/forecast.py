"""GET /scenarios/{id}/forecast and GET /forecast/compare -- the two
endpoints RFP §4.7's every chart, the dashboard, and the compare screen
all render from. No /dashboard, no /charts (architecture §9.1).
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.schemas.forecast import CompareOut, ForecastOut
from app.core.errors import APIError
from app.db.models.user import User
from app.db.session import get_db
from app.engine.types import YearMonth
from app.services.compare_service import CompareService
from app.services.forecast_service import ForecastService

router = APIRouter(tags=["forecast"])


def _resolve_anchor(anchor: str | None) -> YearMonth:
    """The one place "now" gets read for a forecast -- never inside the
    engine, and not inside the services either (they take this as a
    required argument). An explicit ?anchor= reproduces any forecast
    exactly, for QA or a bug report."""
    if anchor is None:
        return YearMonth.from_date(date.today())
    try:
        return YearMonth.parse(anchor)
    except ValueError:
        raise APIError("validation.invalid", {"field": "anchor"}) from None


@router.get("/scenarios/{scenario_id}/forecast", response_model=ForecastOut)
def get_forecast(
    scenario_id: uuid.UUID,
    horizon: int = Query(...),
    anchor: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ForecastOut:
    result = ForecastService(db).forecast(
        user.id, scenario_id, horizon_months=horizon, anchor_month=_resolve_anchor(anchor)
    )
    return ForecastOut.from_result(result)


@router.get("/forecast/compare", response_model=CompareOut)
def compare_forecasts(
    a: uuid.UUID = Query(...),
    b: uuid.UUID = Query(...),
    horizon: int = Query(...),
    anchor: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CompareOut:
    result = CompareService(db).compare(
        user.id, a, b, horizon_months=horizon, anchor_month=_resolve_anchor(anchor)
    )
    return CompareOut.from_result(result)
