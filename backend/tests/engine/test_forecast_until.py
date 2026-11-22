"""`until` ends the forecast on an exact day (UAT-005): the final month is a
partial month and everything before it is exactly what a plain horizon gives."""

from __future__ import annotations

from datetime import date

from hypothesis import given
from hypothesis import strategies as st

from app.engine.forecast import forecast
from app.engine.types import YearMonth
from tests.engine.helpers import txn

ANCHOR = YearMonth(2026, 1)


def _salary_and_rent():
    return [
        txn("salary", "Salary", 500_000, "income", "monthly", "2026-01-25"),
        txn("rent", "Rent", 300_000, "expense", "monthly", "2026-01-01"),
    ]


def test_until_cuts_the_final_month_and_leaves_earlier_months_unchanged() -> None:
    full = forecast(
        current_balance_minor=1_000_000,
        anchor_month=ANCHOR,
        horizon_months=3,
        transactions=_salary_and_rent(),
    )
    cut = forecast(
        current_balance_minor=1_000_000,
        anchor_month=ANCHOR,
        horizon_months=3,
        transactions=_salary_and_rent(),
        until=date(2026, 3, 10),
    )
    assert cut.months[:2] == full.months[:2]
    # March: rent (1st) is in, salary (25th) is after the cut-off.
    assert (cut.months[2].income_minor, cut.months[2].expense_minor) == (0, 300_000)
    assert cut.months[2].closing_balance_minor == full.months[1].closing_balance_minor - 300_000
    assert cut.until == date(2026, 3, 10)


def test_an_occurrence_exactly_on_until_is_included_and_the_next_day_is_not() -> None:
    on_day = forecast(
        current_balance_minor=0,
        anchor_month=ANCHOR,
        horizon_months=1,
        transactions=_salary_and_rent(),
        until=date(2026, 1, 25),
    )
    day_before = forecast(
        current_balance_minor=0,
        anchor_month=ANCHOR,
        horizon_months=1,
        transactions=_salary_and_rent(),
        until=date(2026, 1, 24),
    )
    assert on_day.months[0].income_minor == 500_000
    assert day_before.months[0].income_minor == 0


def test_until_on_the_last_day_of_the_month_equals_the_whole_month() -> None:
    whole = forecast(
        current_balance_minor=0,
        anchor_month=ANCHOR,
        horizon_months=2,
        transactions=_salary_and_rent(),
    )
    cut = forecast(
        current_balance_minor=0,
        anchor_month=ANCHOR,
        horizon_months=2,
        transactions=_salary_and_rent(),
        until=date(2026, 2, 28),
    )
    assert cut.months == whole.months


def test_until_in_the_first_month_of_the_anchor() -> None:
    cut = forecast(
        current_balance_minor=100,
        anchor_month=ANCHOR,
        horizon_months=1,
        transactions=_salary_and_rent(),
        until=date(2026, 1, 1),
    )
    assert (cut.months[0].income_minor, cut.months[0].expense_minor) == (0, 300_000)


def test_until_respects_the_clamp_rule_for_day_31_items() -> None:
    items = [txn("bill", "Bill", 1_000, "expense", "monthly", "2026-01-31")]
    # February's occurrence is clamped to the 28th: in on the 28th, out on the 27th.
    on_28 = forecast(
        current_balance_minor=0,
        anchor_month=ANCHOR,
        horizon_months=2,
        transactions=items,
        until=date(2026, 2, 28),
    )
    on_27 = forecast(
        current_balance_minor=0,
        anchor_month=ANCHOR,
        horizon_months=2,
        transactions=items,
        until=date(2026, 2, 27),
    )
    assert on_28.months[1].expense_minor == 1_000
    assert on_27.months[1].expense_minor == 0


@given(
    day_offset=st.integers(min_value=0, max_value=364),
    start_day=st.integers(min_value=1, max_value=28),
)
def test_closing_balance_reconciles_with_the_included_occurrences(
    day_offset: int, start_day: int
) -> None:
    until = date(2026, 1, 1).fromordinal(date(2026, 1, 1).toordinal() + day_offset)
    horizon = YearMonth(2026, 1).months_until(YearMonth.from_date(until)) + 1
    items = [
        txn("a", "A", 12_345, "income", "weekly", f"2026-01-{start_day:02d}"),
        txn("b", "B", 6_789, "expense", "monthly", "2026-01-15"),
    ]
    ledger = forecast(
        current_balance_minor=50_000,
        anchor_month=ANCHOR,
        horizon_months=horizon,
        transactions=items,
        until=until,
    )
    assert all(occ.on <= until for occ in ledger.occurrences)
    signed = sum(
        occ.amount_minor if occ.direction.value == "income" else -occ.amount_minor
        for occ in ledger.occurrences
    )
    assert ledger.months[-1].closing_balance_minor == 50_000 + signed
