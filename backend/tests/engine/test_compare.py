"""Tests for compare(): month deltas, the null-vs-zero percentage rule, and
the drivers list -- including its completeness invariant."""

from app.engine.compare import compare
from app.engine.forecast import forecast
from app.engine.models import Ledger, ResolvedTransaction
from app.engine.types import DriverChange, YearMonth
from tests.engine.helpers import txn

ANCHOR = YearMonth(2026, 1)
HORIZON = 6


def _forecast(transactions: list[ResolvedTransaction], opening_balance_minor: int = 0) -> Ledger:
    return forecast(
        opening_balance_minor=opening_balance_minor,
        anchor_month=ANCHOR,
        horizon_months=HORIZON,
        transactions=transactions,
    )


def test_percentage_is_none_when_baseline_is_zero() -> None:
    a = _forecast([])
    b = _forecast([txn("t1", "Bonus", 10000, "income", "one_time", "2026-01-01")])

    result = compare(a, b)
    # Month 0's baseline closing balance is 0 -> pct must be None, never 0 or inf.
    assert result.deltas[0].closing_balance_delta_pct is None
    assert result.deltas[0].closing_balance_delta_minor == 10000


def test_driver_added_removed_modified_classification() -> None:
    base_txns = [
        txn("rent", "Rent", 300000, "expense", "monthly", "2026-01-01"),
        txn("savings", "Savings transfer", 50000, "expense", "monthly", "2026-01-01"),
    ]
    scenario_txns = [
        txn("rent", "Rent", 350000, "expense", "monthly", "2026-01-01"),  # modified
        # savings: removed entirely
        txn("mortgage", "Mortgage", 200000, "expense", "monthly", "2026-01-01"),  # added
    ]

    result = compare(_forecast(base_txns), _forecast(scenario_txns))
    by_id = {d.source_id: d for d in result.drivers}

    assert by_id["rent"].change is DriverChange.MODIFIED
    assert by_id["savings"].change is DriverChange.REMOVED
    assert by_id["mortgage"].change is DriverChange.ADDED
    assert len(result.drivers) == 3  # nothing unchanged to drop, nothing extra


def test_unchanged_transaction_is_dropped_from_drivers() -> None:
    shared = [txn("rent", "Rent", 300000, "expense", "monthly", "2026-01-01")]

    result = compare(_forecast(shared), _forecast(shared))
    assert result.drivers == ()


def test_driver_contributions_sum_to_closing_balance_delta() -> None:
    base_txns = [
        txn("rent", "Rent", 300000, "expense", "monthly", "2026-01-01"),
        txn("salary", "Salary", 900000, "income", "monthly", "2026-01-01"),
        txn("savings", "Savings transfer", 50000, "expense", "monthly", "2026-01-01"),
    ]
    scenario_txns = [
        txn("rent", "Rent", 350000, "expense", "monthly", "2026-01-01"),
        txn("salary", "Salary", 900000, "income", "monthly", "2026-01-01"),
        txn("mortgage", "Mortgage", 200000, "expense", "monthly", "2026-01-01"),
        txn("car", "Car loan", 75000, "expense", "biweekly", "2026-01-05"),
    ]
    a = _forecast(base_txns, opening_balance_minor=500000)
    b = _forecast(scenario_txns, opening_balance_minor=500000)

    result = compare(a, b)
    total_contribution = sum(d.total_contribution_minor for d in result.drivers)
    actual_delta = b.months[-1].closing_balance_minor - a.months[-1].closing_balance_minor

    assert total_contribution == actual_delta
