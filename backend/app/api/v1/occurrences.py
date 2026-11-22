"""GET /scenarios/{id}/occurrences?month=YYYY-MM -- the dated entries of one
calendar month, with that month's totals (UAT-007). The Transactions screen's
month view renders from this."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.schemas.occurrences import MonthOccurrencesOut
from app.core.errors import APIError
from app.db.models.user import User
from app.db.session import get_db
from app.engine.types import YearMonth
from app.services.occurrence_service import OccurrenceService

router = APIRouter(prefix="/scenarios", tags=["occurrences"])


@router.get("/{scenario_id}/occurrences", response_model=MonthOccurrencesOut)
def get_month_occurrences(
    scenario_id: uuid.UUID,
    month: str = Query(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MonthOccurrencesOut:
    try:
        parsed = YearMonth.parse(month)
    except ValueError:
        raise APIError("validation.invalid", {"field": "month"}) from None
    return MonthOccurrencesOut.from_result(
        OccurrenceService(db).month(user.id, scenario_id, parsed)
    )
