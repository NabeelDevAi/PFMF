"""GET /scenarios/{id}/forecast and GET /forecast/compare -- the two
endpoints RFP §4.7's every chart, the dashboard, and the compare screen
all render from. No /dashboard, no /charts (architecture §9.1).
"""

from __future__ import annotations

import uuid

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


def _parse_anchor(anchor: str | None) -> YearMonth | None:
    """Pure parsing only -- no default, no clock read. A missing anchor
    is passed through as None; ForecastService is where it gets defaulted
    to balance_as_of (architecture §7.1/§11.4), since that needs a
    settings lookup the service already does and this layer shouldn't
    duplicate."""
    if anchor is None:
        return None
    try:
        return YearMonth.parse(anchor)
    except ValueError:
        raise APIError("validation.invalid", {"field": "anchor"}) from None


@router.get("/scenarios/{scenario_id}/forecast", response_model=ForecastOut)
def get_forecast(
    scenario_id: uuid.UUID,
    horizon: int = Query(...),
    anchor: str | None = Query(None),
    include_occurrences: bool = Query(False),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ForecastOut:
    result = ForecastService(db).forecast(
        user.id, scenario_id, horizon_months=horizon, anchor_month=_parse_anchor(anchor)
    )
    return ForecastOut.from_result(result, include_occurrences=include_occurrences)


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
        user.id, a, b, horizon_months=horizon, anchor_month=_parse_anchor(anchor)
    )
    return CompareOut.from_result(result)
