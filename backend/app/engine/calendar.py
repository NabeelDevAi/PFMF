"""Calendar math. Deliberately tiny -- this is the most scrutinized code in
the module, because the single most common recurrence-engine bug (drift
across short months) lives right here.
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date

from .types import YearMonth


def days_in_month(ym: YearMonth) -> int:
    return monthrange(ym.year, ym.month)[1]


def clamped_date(ym: YearMonth, anchor_day: int) -> date:
    """`anchor_day` clamped into `ym`. Jan 31 -> Feb 28 (or 29 in a leap
    year). Leap years require no special case: they fall out of
    `days_in_month` for free.

    Callers must always pass the *original* anchor day (from the
    transaction's start_date), never a previously generated occurrence's
    day -- that substitution is exactly the clamp-vs-drift bug. See
    expand.py's month-based expansion for where this is enforced.
    """
    return date(ym.year, ym.month, min(anchor_day, days_in_month(ym)))
