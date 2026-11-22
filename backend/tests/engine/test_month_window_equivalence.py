"""Expanding ONE month on its own (what GET /scenarios/{id}/occurrences does)
gives exactly the same occurrences and totals as that month's row inside a
long forecast -- so the month view can never disagree with the forecast."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from app.engine.expand import expand
from app.engine.forecast import forecast
from app.engine.types import Direction, YearMonth
from tests.engine.strategies import transaction_sets

ANCHOR = YearMonth(2026, 1)


@given(txns=transaction_sets(), month_index=st.integers(min_value=0, max_value=35))
@settings(max_examples=200, deadline=None)
def test_single_month_expansion_equals_the_forecast_row(txns, month_index) -> None:
    ledger = forecast(
        current_balance_minor=0, anchor_month=ANCHOR, horizon_months=36, transactions=txns
    )
    month = ANCHOR.add(month_index)
    start, end = month.first_day(), month.last_day()

    occurrences = [occ for txn in txns for occ in expand(txn, start, end)]
    income = sum(o.amount_minor for o in occurrences if o.direction is Direction.INCOME)
    expense = sum(o.amount_minor for o in occurrences if o.direction is Direction.EXPENSE)

    row = ledger.months[month_index]
    assert (income, expense, income - expense) == (
        row.income_minor,
        row.expense_minor,
        row.net_minor,
    )
    in_month = sorted(
        (o.on, o.transaction_id) for o in ledger.occurrences if YearMonth.from_date(o.on) == month
    )
    assert sorted((o.on, o.transaction_id) for o in occurrences) == in_month
