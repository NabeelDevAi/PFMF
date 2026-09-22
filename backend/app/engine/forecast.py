"""The pipeline: expand -> assume -> bucket -> accumulate -> Ledger.

Pure. No database, no network, no date.today(), no randomness, no mutation
of inputs. Same inputs always produce byte-identical output -- this is what
makes the engine independently testable and lets the client's own test
cases be run against it directly.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from .assumptions import Assumptions, apply_assumptions
from .expand import expand
from .models import Ledger, MonthRow, Occurrence, ResolvedTransaction
from .types import Direction, Minor, YearMonth


def forecast(
    *,
    current_balance_minor: Minor,
    anchor_month: YearMonth,
    horizon_months: int,
    transactions: list[ResolvedTransaction],
    assumptions: Assumptions | None = None,
) -> Ledger:
    assumptions = assumptions if assumptions is not None else Assumptions.none()
    window_start = anchor_month.first_day()
    window_end = anchor_month.add(horizon_months).first_day() - timedelta(days=1)

    # 1. EXPAND
    occurrences: list[Occurrence] = []
    for txn in transactions:
        occurrences.extend(expand(txn, window_start, window_end))

    # 2. ASSUME -- no-op in Phase 1; Phase 2 growth/inflation hooks here
    occurrences = apply_assumptions(occurrences, assumptions)

    # Stable ordering: date, then transaction id. Sums don't depend on it,
    # but the month-breakdown screen and any audit output need reproducible
    # ordering, not just reproducible totals.
    occurrences.sort(key=lambda o: (o.on, o.transaction_id))

    # 3. BUCKET
    buckets: dict[YearMonth, list[Minor]] = defaultdict(lambda: [0, 0])
    for occ in occurrences:
        slot = buckets[YearMonth.from_date(occ.on)]
        if occ.direction is Direction.INCOME:
            slot[0] += occ.amount_minor
        else:
            slot[1] += occ.amount_minor

    # 4. ACCUMULATE
    rows: list[MonthRow] = []
    balance = current_balance_minor
    for i in range(horizon_months):
        ym = anchor_month.add(i)
        income, expense = buckets.get(ym, (0, 0))
        net = income - expense
        balance += net
        rows.append(MonthRow(ym, income, expense, net, balance))

    return Ledger(
        anchor_month=anchor_month,
        horizon_months=horizon_months,
        current_balance_minor=current_balance_minor,
        months=tuple(rows),
        occurrences=tuple(occurrences),
    )
