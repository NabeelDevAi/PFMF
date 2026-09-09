"""Comparing two ledgers: month-by-month deltas, plus the "drivers" list
that explains which named transactions account for the difference.

Both ledgers must share an anchor month and horizon -- that alignment is the
caller's (a service's) responsibility to guarantee before calling this.
"""

from __future__ import annotations

from collections import defaultdict

from .models import Comparison, Driver, Ledger, MonthDelta, Occurrence
from .types import DriverChange, Minor


def compare(a: Ledger, b: Ledger) -> Comparison:
    if a.anchor_month != b.anchor_month:
        raise ValueError("cannot compare ledgers with different anchor months")
    if a.horizon_months != b.horizon_months:
        raise ValueError("cannot compare ledgers with different horizons")

    deltas = tuple(
        MonthDelta(
            month=rb.month,
            net_delta_minor=rb.net_minor - ra.net_minor,
            closing_balance_delta_minor=rb.closing_balance_minor - ra.closing_balance_minor,
            closing_balance_delta_pct=_pct(ra.closing_balance_minor, rb.closing_balance_minor),
        )
        for ra, rb in zip(a.months, b.months, strict=True)
    )
    return Comparison(deltas=deltas, drivers=_drivers(a, b))


def _pct(base: Minor, other: Minor) -> float | None:
    if base == 0:
        return None  # the UI renders "--", never 0% or infinity
    return round((other - base) / abs(base) * 100, 2)


def _group_by_source(occurrences: tuple[Occurrence, ...]) -> dict[str, list[Occurrence]]:
    out: dict[str, list[Occurrence]] = defaultdict(list)
    for occ in occurrences:
        out[occ.source_id].append(occ)
    return out


def _drivers(a: Ledger, b: Ledger) -> tuple[Driver, ...]:
    a_by_source = _group_by_source(a.occurrences)
    b_by_source = _group_by_source(b.occurrences)

    out: list[Driver] = []
    for source_id in set(a_by_source) | set(b_by_source):
        a_occs = a_by_source.get(source_id, [])
        b_occs = b_by_source.get(source_id, [])

        a_signed = sum(o.signed_minor for o in a_occs)
        b_signed = sum(o.signed_minor for o in b_occs)
        contribution = b_signed - a_signed

        if contribution == 0:
            continue  # unchanged -- dropped, per the architecture's driver contract

        if not a_occs:
            change = DriverChange.ADDED
        elif not b_occs:
            change = DriverChange.REMOVED
        else:
            change = DriverChange.MODIFIED

        sample = (b_occs or a_occs)[0]  # prefer B's name/direction; direction is immutable anyway
        out.append(
            Driver(
                source_id=source_id,
                name=sample.name,
                direction=sample.direction,
                change=change,
                base_total_minor=sum(o.amount_minor for o in a_occs),
                scenario_total_minor=sum(o.amount_minor for o in b_occs),
                total_contribution_minor=contribution,
            )
        )

    # Ranked by contribution magnitude for the "what's driving this" list;
    # source_id as a tiebreak makes the order fully deterministic regardless
    # of set-iteration order above.
    out.sort(key=lambda d: (-abs(d.total_contribution_minor), d.source_id))
    return tuple(out)
