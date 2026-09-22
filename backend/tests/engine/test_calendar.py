"""Direct unit tests for the calendar helpers -- the smallest, most
scrutinized code in the module."""

from datetime import date

from app.engine.calendar import clamped_date, days_in_month
from app.engine.types import YearMonth


def test_days_in_month_non_leap_february() -> None:
    assert days_in_month(YearMonth(2026, 2)) == 28


def test_days_in_month_leap_february() -> None:
    assert days_in_month(YearMonth(2024, 2)) == 29


def test_days_in_month_thirty_day_month() -> None:
    assert days_in_month(YearMonth(2026, 4)) == 30


def test_clamped_date_no_clamp_needed() -> None:
    assert clamped_date(YearMonth(2026, 1), 15) == date(2026, 1, 15)


def test_clamped_date_clamps_31_to_28_in_non_leap_february() -> None:
    assert clamped_date(YearMonth(2026, 2), 31) == date(2026, 2, 28)


def test_clamped_date_clamps_31_to_29_in_leap_february() -> None:
    assert clamped_date(YearMonth(2024, 2), 31) == date(2024, 2, 29)


def test_clamped_date_clamps_31_to_30_in_april() -> None:
    assert clamped_date(YearMonth(2026, 4), 31) == date(2026, 4, 30)


def test_year_month_add_crosses_year_boundary() -> None:
    assert YearMonth(2025, 11).add(3) == YearMonth(2026, 2)


def test_year_month_add_negative() -> None:
    assert YearMonth(2026, 2).add(-3) == YearMonth(2025, 11)


def test_year_month_months_until() -> None:
    assert YearMonth(2025, 1).months_until(YearMonth(2026, 3)) == 14


def test_year_month_ordering_and_str() -> None:
    assert YearMonth(2026, 1) < YearMonth(2026, 2)
    assert str(YearMonth(2026, 1)) == "2026-01"
    assert YearMonth.parse("2026-09") == YearMonth(2026, 9)
