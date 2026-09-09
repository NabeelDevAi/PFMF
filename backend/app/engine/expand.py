"""Recurrence expansion: one resolved transaction + a window -> every
occurrence it produces inside that window.

The highest-risk code in the product. See calendar.py for the clamp rule
this all rests on, and tests/engine/fixtures/ for the named edge cases this
is written test-first against.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, timedelta

from .calendar import clamped_date
from .models import Occurrence, ResolvedTransaction
from .types import Recurrence, YearMonth

DAY_INTERVALS = {Recurrence.WEEKLY: 7, Recurrence.BIWEEKLY: 14}
MONTH_INTERVALS = {
    Recurrence.MONTHLY: 1,
    Recurrence.QUARTERLY: 3,
    Recurrence.SEMIANNUAL: 6,
    Recurrence.ANNUAL: 12,
}


def expand(txn: ResolvedTransaction, window_start: date, window_end: date) -> Iterator[Occurrence]:
    """Every occurrence of `txn` inside [window_start, window_end], both
    boundaries inclusive."""

    if txn.recurrence is Recurrence.ONE_TIME:
        if window_start <= txn.start_date <= window_end:
            yield _occ(txn, txn.start_date)
        return

    hard_end = min(txn.end_date, window_end) if txn.end_date else window_end
    if txn.start_date > hard_end:
        # Ended before the window (or before its own first occurrence).
        # Valid, not an error -- zero occurrences.
        return

    if txn.recurrence in DAY_INTERVALS:
        yield from _expand_day_based(txn, window_start, hard_end)
    else:
        yield from _expand_month_based(txn, window_start, hard_end)


def _expand_day_based(
    txn: ResolvedTransaction, window_start: date, hard_end: date
) -> Iterator[Occurrence]:
    step = DAY_INTERVALS[txn.recurrence]

    # Fast-forward to the first occurrence at or after the window, without
    # generating (and discarding) every occurrence before it.
    current = txn.start_date
    if current < window_start:
        gap = (window_start - current).days
        current += timedelta(days=((gap + step - 1) // step) * step)

    while current <= hard_end:
        yield _occ(txn, current)
        current += timedelta(days=step)


def _expand_month_based(
    txn: ResolvedTransaction, window_start: date, hard_end: date
) -> Iterator[Occurrence]:
    interval = MONTH_INTERVALS[txn.recurrence]
    anchor_day = txn.start_date.day  # ALWAYS from start_date -- never from a generated occurrence
    start_ym = YearMonth.from_date(txn.start_date)

    # Fast-forward close to the window, then step back one interval as a
    # safety margin so a clamped boundary occurrence is never skipped by
    # rounding down. The window/hard_end checks below are authoritative --
    # this only skips the guaranteed-irrelevant iterations before it.
    n = 0
    if txn.start_date < window_start:
        months_gap = start_ym.months_until(YearMonth.from_date(window_start))
        n = max(0, (months_gap // interval) - 1)

    while True:
        occurrence_date = clamped_date(start_ym.add(n * interval), anchor_day)
        if occurrence_date > hard_end:
            return
        if occurrence_date >= window_start and occurrence_date >= txn.start_date:
            yield _occ(txn, occurrence_date)
        n += 1


def _occ(txn: ResolvedTransaction, on: date) -> Occurrence:
    return Occurrence(
        transaction_id=txn.id,
        source_id=txn.source_id,
        origin=txn.origin,
        name=txn.name,
        on=on,
        amount_minor=txn.amount_minor,
        direction=txn.direction,
    )
