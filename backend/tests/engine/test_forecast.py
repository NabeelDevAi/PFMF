"""Golden-fixture suite: every *.json file under tests/engine/fixtures/
(including tests/engine/fixtures/client/, reserved for the client's own
independently-verified test cases once obtained) is discovered and run
automatically. Adding a case is adding a file -- no code change.

Also covers the one named edge case that isn't a fixture: 120-month weekly
horizon, where hand-computing exact expected values isn't practical -- this
is a performance-plus-correctness check instead (correctness via the
reconciliation invariant, which is what actually matters for that case).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from app.engine.forecast import forecast
from app.engine.types import YearMonth
from tests.engine.helpers import txn, txn_from_dict

FIXTURES_DIR = Path(__file__).parent / "fixtures"
FIXTURE_FILES = sorted(FIXTURES_DIR.rglob("*.json"))


@pytest.mark.parametrize("fixture_path", FIXTURE_FILES, ids=lambda p: p.stem)
def test_golden_fixture(fixture_path: Path) -> None:
    case = json.loads(fixture_path.read_text())
    transactions = [txn_from_dict(t) for t in case["transactions"]]

    ledger = forecast(
        current_balance_minor=case["current_balance_minor"],
        anchor_month=YearMonth.parse(case["anchor_month"]),
        horizon_months=case["horizon_months"],
        transactions=transactions,
    )

    assert len(ledger.months) == len(case["expected_months"]), (
        f"{case['name']}: expected {len(case['expected_months'])} month rows, "
        f"got {len(ledger.months)}"
    )
    for row, expected in zip(ledger.months, case["expected_months"], strict=True):
        assert str(row.month) == expected["month"], case["name"]
        assert row.income_minor == expected["income_minor"], case["name"]
        assert row.expense_minor == expected["expense_minor"], case["name"]
        assert row.net_minor == expected["net_minor"], case["name"]
        assert row.closing_balance_minor == expected["closing_balance_minor"], case["name"]


def test_m1_case_27_2_horizon_choice_does_not_change_shared_months() -> None:
    """M1 case 27.2: any month appearing in more than one horizon must
    show identical figures in each -- run the shared Base Plan of
    fixtures/m1/27.1.json at all four client-facing horizons and compare
    December 2026 (month index 11) across every one."""
    case = json.loads((FIXTURES_DIR / "m1" / "27.1.json").read_text())
    transactions = [txn_from_dict(t) for t in case["transactions"]]

    december_2026_rows = []
    for horizon in (12, 36, 60, 120):
        ledger = forecast(
            current_balance_minor=case["current_balance_minor"],
            anchor_month=YearMonth.parse(case["anchor_month"]),
            horizon_months=horizon,
            transactions=transactions,
        )
        december_2026_rows.append(ledger.months[11])

    assert all(row == december_2026_rows[0] for row in december_2026_rows)
    assert str(december_2026_rows[0].month) == "2026-12"


def test_weekly_over_120_months_is_fast_and_reconciles() -> None:
    """Named edge case from architecture §12.2: 120-month horizon, weekly
    recurrence -> ~520 occurrences from this one transaction alone. Not a
    golden fixture (hand-computing 120 months of weekly totals isn't
    practical) -- correctness here means the reconciliation invariant holds
    and it runs in well under a second, not exact hand-verified values."""
    t = txn("t1", "Weekly wage", 50000, "income", "weekly", "2020-01-03")

    started = time.perf_counter()
    ledger = forecast(
        current_balance_minor=0,
        anchor_month=YearMonth(2026, 1),
        horizon_months=120,
        transactions=[t],
    )
    elapsed = time.perf_counter() - started

    assert elapsed < 1.0, f"120-month weekly forecast took {elapsed:.3f}s -- too slow"
    assert len(ledger.months) == 120
    assert ledger.months[-1].closing_balance_minor == sum(
        o.signed_minor for o in ledger.occurrences
    )
    assert len(ledger.occurrences) > 400  # ~520 expected; loose bound, not exact
