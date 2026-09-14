"""Hypothesis property tests (architecture §12.3, Tier 2 #6) -- generated
fuzzing over the same invariants tests/engine/test_invariants.py checks
with a curated, hand-picked set of cases. Both stay: the hand-picked
cases pin specific, understandable scenarios as permanent regression
tests; these generate hundreds of randomized ones per run and shrink any
failure to a minimal reproducer.

Isolation is the fourth invariant from §12.3 and is NOT here, for the
same reason it isn't in test_invariants.py: the engine has no concept of
scenarios or overlays. Its Hypothesis test lives in
tests/services/test_scenario_resolver.py, against the real resolver and
the real database.
"""

from __future__ import annotations

from hypothesis import given, settings

from app.engine.compare import compare
from app.engine.forecast import forecast
from app.engine.types import YearMonth
from tests.engine.strategies import HORIZONS, OPENING_BALANCES, transaction_sets

ANCHOR = YearMonth(2026, 1)


@given(txns=transaction_sets(), opening=OPENING_BALANCES, horizon=HORIZONS)
@settings(max_examples=200, deadline=None)
def test_reconciliation_property(txns, opening, horizon) -> None:
    """Final balance equals opening plus the signed sum of every
    occurrence that actually landed in the window -- RFP §10's core
    criterion, mechanised."""
    ledger = forecast(
        opening_balance_minor=opening,
        anchor_month=ANCHOR,
        horizon_months=horizon,
        transactions=txns,
    )
    expected = opening + sum(o.signed_minor for o in ledger.occurrences)
    assert ledger.months[-1].closing_balance_minor == expected


@given(txns=transaction_sets(), opening=OPENING_BALANCES, horizon=HORIZONS)
@settings(max_examples=200, deadline=None)
def test_determinism_property(txns, opening, horizon) -> None:
    """Same inputs, run twice, byte-identical output."""
    first = forecast(
        opening_balance_minor=opening,
        anchor_month=ANCHOR,
        horizon_months=horizon,
        transactions=txns,
    )
    second = forecast(
        opening_balance_minor=opening,
        anchor_month=ANCHOR,
        horizon_months=horizon,
        transactions=txns,
    )
    assert first == second


@given(
    txns_a=transaction_sets(),
    txns_b=transaction_sets(),
    opening=OPENING_BALANCES,
    horizon=HORIZONS,
)
@settings(max_examples=200, deadline=None)
def test_driver_completeness_property(txns_a, txns_b, opening, horizon) -> None:
    """Driver contributions sum exactly to the closing-balance delta.
    txns_a and txns_b are generated independently but both assign ids
    sequentially from t0 -- overlapping ids land as "modified" (same
    source, different value), ids present in only one side land as
    added/removed. That's exactly the semantics compare() assumes, so
    this organically fuzzes all three change types without needing to
    orchestrate it explicitly."""
    a = forecast(
        opening_balance_minor=opening,
        anchor_month=ANCHOR,
        horizon_months=horizon,
        transactions=txns_a,
    )
    b = forecast(
        opening_balance_minor=opening,
        anchor_month=ANCHOR,
        horizon_months=horizon,
        transactions=txns_b,
    )
    result = compare(a, b)
    total_contribution = sum(d.total_contribution_minor for d in result.drivers)
    actual_delta = b.months[-1].closing_balance_minor - a.months[-1].closing_balance_minor
    assert total_contribution == actual_delta
