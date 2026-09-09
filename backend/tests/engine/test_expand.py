"""Direct unit tests for expand() with window boundaries that aren't simply
"the whole horizon from anchor month 1" -- the fixture-driven forecast tests
cover the named edge cases end-to-end; these poke at expand() in isolation
with boundaries the pipeline itself never happens to produce, since expand()
is a public engine function in its own right (architecture doc §7.3)."""

from datetime import date

from app.engine.expand import expand
from tests.engine.helpers import txn


def _dates(occs) -> list[date]:
    return [o.on for o in occs]


def test_window_not_aligned_to_month_start() -> None:
    """window_start mid-month must not exclude a later same-month occurrence."""
    t = txn("t1", "Rent", 1000, "expense", "monthly", "2026-01-31")
    occs = list(expand(t, date(2026, 1, 15), date(2026, 3, 31)))
    assert _dates(occs) == [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31)]


def test_one_time_exactly_on_window_start_is_included() -> None:
    t = txn("t1", "Bonus", 1000, "income", "one_time", "2026-01-01")
    occs = list(expand(t, date(2026, 1, 1), date(2026, 12, 31)))
    assert _dates(occs) == [date(2026, 1, 1)]


def test_one_time_exactly_on_window_end_is_included() -> None:
    t = txn("t1", "Bonus", 1000, "income", "one_time", "2026-12-31")
    occs = list(expand(t, date(2026, 1, 1), date(2026, 12, 31)))
    assert _dates(occs) == [date(2026, 12, 31)]


def test_biweekly_interval_is_fourteen_days() -> None:
    t = txn("t1", "Pay", 1000, "income", "biweekly", "2026-01-01")
    occs = list(expand(t, date(2026, 1, 1), date(2026, 2, 28)))
    assert _dates(occs) == [
        date(2026, 1, 1),
        date(2026, 1, 15),
        date(2026, 1, 29),
        date(2026, 2, 12),
        date(2026, 2, 26),
    ]


def test_quarterly_skips_two_months_between_occurrences() -> None:
    t = txn("t1", "Insurance", 1000, "expense", "quarterly", "2026-01-31")
    occs = list(expand(t, date(2026, 1, 1), date(2026, 12, 31)))
    assert _dates(occs) == [
        date(2026, 1, 31),
        date(2026, 4, 30),  # clamped: April has 30 days
        date(2026, 7, 31),
        date(2026, 10, 31),
    ]


def test_transaction_entirely_before_window_yields_nothing() -> None:
    t = txn("t1", "Old", 1000, "expense", "monthly", "2020-01-01", end_date="2020-06-01")
    occs = list(expand(t, date(2026, 1, 1), date(2026, 12, 31)))
    assert occs == []


def test_transaction_entirely_after_window_yields_nothing() -> None:
    t = txn("t1", "Future", 1000, "expense", "monthly", "2030-01-01")
    occs = list(expand(t, date(2026, 1, 1), date(2026, 12, 31)))
    assert occs == []
