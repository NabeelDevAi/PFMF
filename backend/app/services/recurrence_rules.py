"""The one place that decides whether a (recurrence, interval, unit) triple is
valid (D-08 amended 2026-11-22): `custom` needs a whole-number interval from
1 to 999 and a unit; every other recurrence must carry neither."""

from __future__ import annotations

from datetime import date
from itertools import islice

from app.core.errors import APIError
from app.domain.enums import (
    MAX_RECURRENCE_INTERVAL,
    MIN_RECURRENCE_INTERVAL,
    Direction,
    Recurrence,
    RecurrenceUnit,
)
from app.engine import types as engine_types
from app.engine.expand import expand
from app.engine.models import ResolvedTransaction

# Far enough for any open-ended preview; the same upper bound the API puts on
# every transaction date.
_PREVIEW_HORIZON = date(2100, 12, 31)


def check_recurrence(
    recurrence: Recurrence,
    interval: int | None,
    unit: RecurrenceUnit | None,
    *,
    interval_field: str = "recurrence_interval",
    unit_field: str = "recurrence_unit",
) -> tuple[int | None, RecurrenceUnit | None]:
    """Returns the (interval, unit) to store. Raises `validation.invalid`
    (with the offending field) when the combination is not allowed."""
    if recurrence is Recurrence.CUSTOM:
        if interval is None or not MIN_RECURRENCE_INTERVAL <= interval <= MAX_RECURRENCE_INTERVAL:
            raise APIError("validation.invalid", {"field": interval_field})
        if unit is None:
            raise APIError("validation.invalid", {"field": unit_field})
        return interval, unit
    if interval is not None:
        raise APIError("validation.invalid", {"field": interval_field})
    if unit is not None:
        raise APIError("validation.invalid", {"field": unit_field})
    return None, None


def check_dates(recurrence: Recurrence, start_date: date, end_date: date | None) -> None:
    """Date rules shared by create, update and the preview."""
    if end_date is not None and end_date < start_date:
        raise APIError("transaction.end_before_start", {"field": "end_date"})
    if recurrence is Recurrence.ONE_TIME and end_date is not None:
        raise APIError("transaction.one_time_has_end_date", {"field": "end_date"})


def preview_dates(
    recurrence: Recurrence,
    interval: int | None,
    unit: RecurrenceUnit | None,
    start_date: date,
    end_date: date | None,
    count: int,
) -> list[date]:
    """The first `count` occurrence dates of a rule that has not been saved,
    computed by the same engine `expand` the forecast uses, so what the user
    previews is exactly what the forecast will contain."""
    check_dates(recurrence, start_date, end_date)
    interval, unit = check_recurrence(recurrence, interval, unit)
    txn = ResolvedTransaction(
        id="preview",
        source_id="preview",
        origin=engine_types.Origin.OWN,
        name="preview",
        amount_minor=1,
        direction=engine_types.Direction(Direction.EXPENSE.value),
        category_id=None,
        recurrence=engine_types.Recurrence(recurrence.value),
        start_date=start_date,
        end_date=end_date,
        recurrence_interval=interval,
        recurrence_unit=engine_types.RecurrenceUnit(unit.value) if unit else None,
    )
    window_end = min(end_date, _PREVIEW_HORIZON) if end_date else _PREVIEW_HORIZON
    return [occ.on for occ in islice(expand(txn, start_date, window_end), count)]
