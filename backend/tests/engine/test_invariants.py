"""Hand-picked stand-ins for the Hypothesis property tests the plan defers
to the M6 hardening milestone (see claude_docs/backend-plan/10-testing-strategy.md).
These exercise the same invariants -- reconciliation, determinism, and driver
completeness -- on a curated set of deliberately varied cases, so the
acceptance-critical guarantees are never left unverified in the meantime.

Isolation (arbitrary overlays on scenario B never affecting scenario A) is
NOT tested here -- the engine has no concept of scenarios or overlays at
all. That invariant belongs to the scenario resolver, built in milestone M4.
"""

from __future__ import annotations

from app.engine.compare import compare
from app.engine.forecast import forecast
from app.engine.types import YearMonth
from tests.engine.helpers import txn

RECONCILIATION_CASES: list[dict] = [
    {
        "opening_balance_minor": 0,
        "anchor_month": YearMonth(2026, 1),
        "horizon_months": 12,
        "transactions": [
            txn("t1", "Salary", 900000, "income", "monthly", "2026-01-25"),
            txn("t2", "Rent", 300000, "expense", "monthly", "2026-01-01"),
            txn("t3", "Groceries", 15000, "expense", "weekly", "2026-01-03"),
        ],
    },
    {
        # Negative opening balance -- already in overdraft at the anchor month.
        "opening_balance_minor": -250000,
        "anchor_month": YearMonth(2026, 6),
        "horizon_months": 36,
        "transactions": [
            txn("t1", "Freelance income", 120000, "income", "biweekly", "2026-06-10"),
            txn(
                "t2",
                "Car loan",
                180000,
                "expense",
                "monthly",
                "2026-06-15",
                end_date="2028-06-15",
            ),
            txn("t3", "Annual insurance", 500000, "expense", "annual", "2026-08-31"),
            txn("t4", "One-off refund", 200000, "income", "one_time", "2026-09-01"),
        ],
    },
    {
        # A transaction with every recurrence type represented at once,
        # several starting long before the anchor month.
        "opening_balance_minor": 1000000,
        "anchor_month": YearMonth(2027, 1),
        "horizon_months": 120,
        "transactions": [
            txn("t1", "Salary", 1000000, "income", "monthly", "2018-01-31"),
            txn("t2", "Rent", 400000, "expense", "monthly", "2020-05-31"),
            txn("t3", "Weekly allowance", 20000, "expense", "weekly", "2026-01-01"),
            txn("t4", "Biweekly side gig", 60000, "income", "biweekly", "2026-03-15"),
            txn("t5", "Quarterly bonus", 300000, "income", "quarterly", "2024-02-29"),
            txn("t6", "Semiannual tax", 150000, "expense", "semiannual", "2026-06-30"),
            txn("t7", "Annual subscription", 25000, "expense", "annual", "2024-02-29"),
            txn("t8", "One-time gift", 500000, "income", "one_time", "2027-06-01"),
        ],
    },
    {
        # Everything ends partway through the horizon.
        "opening_balance_minor": 0,
        "anchor_month": YearMonth(2026, 1),
        "horizon_months": 24,
        "transactions": [
            txn(
                "t1",
                "Short-term contract",
                700000,
                "income",
                "monthly",
                "2026-01-01",
                end_date="2026-08-01",
            ),
            txn(
                "t2",
                "Temporary storage rental",
                30000,
                "expense",
                "monthly",
                "2026-01-15",
                end_date="2026-01-15",
            ),
        ],
    },
]


def test_reconciliation_holds_across_varied_cases() -> None:
    for case in RECONCILIATION_CASES:
        ledger = forecast(**case)
        expected = case["opening_balance_minor"] + sum(o.signed_minor for o in ledger.occurrences)
        assert ledger.months[-1].closing_balance_minor == expected, case["transactions"]


def test_determinism_same_inputs_identical_output() -> None:
    for case in RECONCILIATION_CASES:
        first = forecast(**case)
        second = forecast(**case)
        assert first == second


def test_driver_completeness_across_a_larger_diff() -> None:
    a_txns = RECONCILIATION_CASES[2]["transactions"]
    b_txns = [
        txn("t1", "Salary", 1100000, "income", "monthly", "2018-01-31"),  # modified
        *a_txns[1:-1],  # unchanged
        # a_txns[-1] ("t8", one-time gift) dropped -- removed
        txn("t9", "New side income", 90000, "income", "weekly", "2027-01-01"),  # added
    ]

    anchor = YearMonth(2027, 1)
    horizon = 120
    a = forecast(
        opening_balance_minor=1000000,
        anchor_month=anchor,
        horizon_months=horizon,
        transactions=a_txns,
    )
    b = forecast(
        opening_balance_minor=1000000,
        anchor_month=anchor,
        horizon_months=horizon,
        transactions=b_txns,
    )

    result = compare(a, b)
    total_contribution = sum(d.total_contribution_minor for d in result.drivers)
    actual_delta = b.months[-1].closing_balance_minor - a.months[-1].closing_balance_minor
    assert total_contribution == actual_delta
