"""Custom recurrence ("every N days / weeks / months / years", UAT-004):
exact dates for the client's own examples, the clamp-never-drift rule at
month ends and leap years, and equivalence with the seven named rules."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.engine.expand import expand
from app.engine.models import ResolvedTransaction
from app.engine.types import Direction, Origin, Recurrence, RecurrenceUnit


def _txn(
    recurrence: Recurrence,
    start: str,
    end: str | None = None,
    *,
    interval: int | None = None,
    unit: RecurrenceUnit | None = None,
) -> ResolvedTransaction:
    return ResolvedTransaction(
        id="t",
        source_id="t",
        origin=Origin.OWN,
        name="t",
        amount_minor=100,
        direction=Direction.EXPENSE,
        category_id=None,
        recurrence=recurrence,
        start_date=date.fromisoformat(start),
        end_date=date.fromisoformat(end) if end else None,
        recurrence_interval=interval,
        recurrence_unit=unit,
    )


def _custom(start: str, interval: int, unit: RecurrenceUnit, end: str | None = None):
    return _txn(Recurrence.CUSTOM, start, end, interval=interval, unit=unit)


def _dates(txn: ResolvedTransaction, window_start: str, window_end: str) -> list[str]:
    return [
        o.on.isoformat()
        for o in expand(txn, date.fromisoformat(window_start), date.fromisoformat(window_end))
    ]


# ---- the client's examples ---------------------------------------------------


def test_every_10_days() -> None:
    assert _dates(_custom("2026-01-01", 10, RecurrenceUnit.DAY), "2026-01-01", "2026-02-15") == [
        "2026-01-01",
        "2026-01-11",
        "2026-01-21",
        "2026-01-31",
        "2026-02-10",
    ]


def test_every_4_months_keeps_the_anchor_day_and_clamps_short_months() -> None:
    # Anchor day 31: Jan 31, May 31, Sep 30 (clamped), Jan 31 again (no drift).
    assert _dates(_custom("2026-01-31", 4, RecurrenceUnit.MONTH), "2026-01-01", "2027-02-28") == [
        "2026-01-31",
        "2026-05-31",
        "2026-09-30",
        "2027-01-31",
    ]


def test_every_6_months() -> None:
    assert _dates(_custom("2026-08-31", 6, RecurrenceUnit.MONTH), "2026-01-01", "2028-01-01") == [
        "2026-08-31",
        "2027-02-28",
        "2027-08-31",
    ]


def test_every_2_years_from_feb_29_follows_leap_years() -> None:
    assert _dates(_custom("2024-02-29", 2, RecurrenceUnit.YEAR), "2024-01-01", "2032-12-31") == [
        "2024-02-29",
        "2026-02-28",
        "2028-02-29",
        "2030-02-28",
        "2032-02-29",
    ]


def test_every_year_from_feb_29_returns_to_the_29th_in_leap_years() -> None:
    assert _dates(_custom("2024-02-29", 1, RecurrenceUnit.YEAR), "2024-01-01", "2028-12-31") == [
        "2024-02-29",
        "2025-02-28",
        "2026-02-28",
        "2027-02-28",
        "2028-02-29",
    ]


def test_every_3_weeks() -> None:
    assert _dates(_custom("2026-01-05", 3, RecurrenceUnit.WEEK), "2026-01-01", "2026-03-31") == [
        "2026-01-05",
        "2026-01-26",
        "2026-02-16",
        "2026-03-09",
        "2026-03-30",
    ]


# ---- month-end and leap-day anchors -----------------------------------------


@pytest.mark.parametrize(
    ("start", "february"),
    [("2026-01-29", "2027-02-28"), ("2026-01-30", "2027-02-28"), ("2026-01-31", "2027-02-28")],
)
def test_anchor_days_29_30_31_clamp_in_a_non_leap_february(start: str, february: str) -> None:
    dates = _dates(_custom(start, 1, RecurrenceUnit.MONTH), "2027-02-01", "2027-02-28")
    assert dates == [february]


@pytest.mark.parametrize("start", ["2027-01-29", "2027-01-30", "2027-01-31"])
def test_anchor_days_29_30_31_in_a_leap_february(start: str) -> None:
    dates = _dates(_custom(start, 1, RecurrenceUnit.MONTH), "2028-02-01", "2028-02-29")
    assert dates == ["2028-02-29"]


def test_clamped_month_does_not_shift_the_following_months() -> None:
    # Jan 31 every month: Feb 28, then Mar 31 (not Mar 28).
    dates = _dates(_custom("2026-01-31", 1, RecurrenceUnit.MONTH), "2026-01-01", "2026-04-30")
    assert dates == ["2026-01-31", "2026-02-28", "2026-03-31", "2026-04-30"]


def test_end_date_is_inclusive_and_start_after_window_yields_nothing() -> None:
    txn = _custom("2026-01-01", 10, RecurrenceUnit.DAY, end="2026-01-21")
    assert _dates(txn, "2026-01-01", "2026-12-31") == ["2026-01-01", "2026-01-11", "2026-01-21"]
    assert _dates(_custom("2027-01-01", 5, RecurrenceUnit.DAY), "2026-01-01", "2026-12-31") == []


def test_window_starting_late_still_finds_the_right_dates() -> None:
    # Fast-forward path: the first occurrence is far before the window.
    assert _dates(_custom("2020-01-01", 45, RecurrenceUnit.DAY), "2026-03-01", "2026-04-30") == [
        (date(2020, 1, 1) + timedelta(days=45 * n)).isoformat()
        for n in range(150)
        if date(2026, 3, 1) <= date(2020, 1, 1) + timedelta(days=45 * n) <= date(2026, 4, 30)
    ]


def test_a_custom_rule_without_interval_or_unit_is_rejected_by_the_engine() -> None:
    with pytest.raises(ValueError):
        list(expand(_txn(Recurrence.CUSTOM, "2026-01-01"), date(2026, 1, 1), date(2026, 12, 31)))
    with pytest.raises(ValueError):
        list(
            expand(
                _txn(Recurrence.CUSTOM, "2026-01-01", interval=0, unit=RecurrenceUnit.DAY),
                date(2026, 1, 1),
                date(2026, 12, 31),
            )
        )


# ---- equivalence with the seven named rules (property tests) ----------------

_EQUIVALENT = [
    (Recurrence.WEEKLY, 7, RecurrenceUnit.DAY),
    (Recurrence.WEEKLY, 1, RecurrenceUnit.WEEK),
    (Recurrence.BIWEEKLY, 14, RecurrenceUnit.DAY),
    (Recurrence.BIWEEKLY, 2, RecurrenceUnit.WEEK),
    (Recurrence.MONTHLY, 1, RecurrenceUnit.MONTH),
    (Recurrence.QUARTERLY, 3, RecurrenceUnit.MONTH),
    (Recurrence.SEMIANNUAL, 6, RecurrenceUnit.MONTH),
    (Recurrence.ANNUAL, 12, RecurrenceUnit.MONTH),
    (Recurrence.ANNUAL, 1, RecurrenceUnit.YEAR),
]


@pytest.mark.parametrize(("named", "interval", "unit"), _EQUIVALENT)
@given(
    start=st.dates(min_value=date(2015, 1, 1), max_value=date(2035, 12, 31)),
    window_offset=st.integers(min_value=-400, max_value=4000),
    window_len=st.integers(min_value=1, max_value=1500),
    end_offset=st.none() | st.integers(min_value=0, max_value=3000),
)
@settings(max_examples=60, deadline=None)
def test_custom_equals_the_matching_named_rule(
    named: Recurrence,
    interval: int,
    unit: RecurrenceUnit,
    start: date,
    window_offset: int,
    window_len: int,
    end_offset: int | None,
) -> None:
    end = start + timedelta(days=end_offset) if end_offset is not None else None
    w_start = start + timedelta(days=window_offset)
    w_end = w_start + timedelta(days=window_len)
    expected = [
        o.on
        for o in expand(_txn(named, start.isoformat(), end and end.isoformat()), w_start, w_end)
    ]
    actual = [
        o.on
        for o in expand(
            _custom(start.isoformat(), interval, unit, end and end.isoformat()), w_start, w_end
        )
    ]
    assert actual == expected


@given(
    start=st.dates(min_value=date(2015, 1, 1), max_value=date(2030, 12, 31)),
    interval=st.integers(min_value=1, max_value=999),
    unit=st.sampled_from(list(RecurrenceUnit)),
    window_offset=st.integers(min_value=0, max_value=5000),
    window_len=st.integers(min_value=1, max_value=800),
)
@settings(max_examples=150, deadline=None)
def test_windowed_expansion_equals_the_full_expansion_filtered(
    start: date, interval: int, unit: RecurrenceUnit, window_offset: int, window_len: int
) -> None:
    """The fast-forward shortcut must never skip or invent an occurrence."""
    txn = _custom(start.isoformat(), interval, unit)
    w_start = start + timedelta(days=window_offset)
    w_end = w_start + timedelta(days=window_len)
    windowed = [o.on for o in expand(txn, w_start, w_end)]
    everything = [o.on for o in expand(txn, start, w_end)]
    assert windowed == [d for d in everything if w_start <= d <= w_end]
    assert windowed == sorted(set(windowed))
