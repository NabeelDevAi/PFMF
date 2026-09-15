"""Hypothesis strategies for generating realistic ResolvedTransaction
sets. Shared between tests/engine/test_properties.py and the resolver's
isolation property test (tests/services/test_scenario_resolver.py) --
same reasoning either way: a strategy that's too loose generates
nonsense inputs the engine was never meant to handle; too tight and it
stops being fuzzing.
"""

from __future__ import annotations

from datetime import date

from hypothesis import strategies as st

from app.engine.models import ResolvedTransaction
from app.engine.types import Direction, Origin, Recurrence

# Wide enough to cross several leap years and force clamp behavior
# (start dates on the 29th/30th/31st), narrow enough that YearMonth
# arithmetic and window math stay well away from any edge.
_EARLIEST_START = date(2015, 1, 1)
_LATEST_START = date(2035, 12, 31)
_LATEST_END = date(2040, 12, 31)


@st.composite
def _transaction_spec(draw: st.DrawFn) -> dict:
    recurrence = draw(st.sampled_from(list(Recurrence)))
    start_date = draw(st.dates(min_value=_EARLIEST_START, max_value=_LATEST_START))

    if recurrence is Recurrence.ONE_TIME:
        end_date = None
    else:
        end_date = draw(st.none() | st.dates(min_value=start_date, max_value=_LATEST_END))

    return {
        "amount_minor": draw(st.integers(min_value=1, max_value=5_000_000)),
        "direction": draw(st.sampled_from(list(Direction))),
        "recurrence": recurrence,
        "start_date": start_date,
        "end_date": end_date,
    }


def _build(specs: list[dict], origin: Origin) -> list[ResolvedTransaction]:
    # Sequential ids assigned after generation, not as part of the
    # per-transaction strategy -- guarantees uniqueness within one
    # generated set regardless of how Hypothesis shrinks the list.
    out = []
    for i, spec in enumerate(specs):
        tid = f"t{i}"
        out.append(
            ResolvedTransaction(
                id=tid, source_id=tid, origin=origin, name=tid, category_id=None, **spec
            )
        )
    return out


def transaction_sets(*, min_size: int = 0, max_size: int = 12) -> st.SearchStrategy[list]:
    """A list of ResolvedTransaction, all origin=OWN -- origin doesn't
    affect any engine computation, only how compare() labels a driver."""
    return st.lists(_transaction_spec(), min_size=min_size, max_size=max_size).map(
        lambda specs: _build(specs, Origin.OWN)
    )


HORIZONS = st.sampled_from([12, 36, 60, 120])
CURRENT_BALANCES = st.integers(min_value=-(10**9), max_value=10**9)
