"""The plain value objects that flow through the engine pipeline.

All frozen (immutable) -- the engine never mutates its inputs, and nothing
downstream should be able to mutate its outputs either.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .types import Direction, DriverChange, Minor, Origin, Recurrence, YearMonth


@dataclass(frozen=True)
class ResolvedTransaction:
    """What the engine actually consumes -- already flattened by the
    scenario resolver (a service, outside the engine). By the time this
    reaches app/engine/, there is no notion of Base or overlay left in it
    except the `origin` tag, carried through for comparison drivers."""

    id: str
    source_id: str  # the Base transaction's id if inherited/overridden, else this id
    origin: Origin
    name: str
    amount_minor: Minor  # always positive
    direction: Direction
    category_id: str | None
    recurrence: Recurrence
    start_date: date
    end_date: date | None  # None = open-ended


@dataclass(frozen=True)
class Occurrence:
    """One dated, signed instance of a transaction. Computed, never stored."""

    transaction_id: str
    source_id: str
    origin: Origin
    name: str
    on: date
    amount_minor: Minor
    direction: Direction

    @property
    def signed_minor(self) -> Minor:
        return self.amount_minor if self.direction is Direction.INCOME else -self.amount_minor


@dataclass(frozen=True)
class MonthRow:
    month: YearMonth
    income_minor: Minor
    expense_minor: Minor
    net_minor: Minor
    closing_balance_minor: Minor


@dataclass(frozen=True)
class Ledger:
    """The engine's output. `occurrences` is retained deliberately -- it
    powers the month-breakdown screen and comparison drivers without a
    second pass or a second query."""

    anchor_month: YearMonth
    horizon_months: int
    current_balance_minor: Minor
    months: tuple[MonthRow, ...]
    occurrences: tuple[Occurrence, ...]


@dataclass(frozen=True)
class MonthDelta:
    month: YearMonth
    net_delta_minor: Minor
    closing_balance_delta_minor: Minor
    closing_balance_delta_pct: float | None  # None when the baseline month is 0


@dataclass(frozen=True)
class Driver:
    """One named transaction's contribution to the difference between two
    ledgers, keyed by its stable source_id so it survives renaming via
    override. `total_contribution_minor` is the signed delta this source
    contributed to the closing-balance difference; driver contributions sum
    exactly to it across all drivers (the completeness property test)."""

    source_id: str
    name: str
    direction: Direction
    change: DriverChange
    base_total_minor: Minor  # magnitude: sum of amount_minor in ledger A (0 if absent)
    scenario_total_minor: Minor  # magnitude: sum of amount_minor in ledger B (0 if absent)
    total_contribution_minor: Minor  # signed delta to the closing balance
    active_months: int  # distinct months this source occurs in (whichever side has it --
    # B preferred, matching `name`/`direction`'s own preference below). Lets a client compute
    # this driver's real per-occurrence rate (total_contribution_minor / active_months) instead
    # of diluting it across the whole horizon, which understates anything that starts, ends, or
    # was added/removed partway through -- e.g. a mortgage added 2 months into a 120-month
    # horizon would otherwise show as ~2% smaller per month than its real, steady cost.


@dataclass(frozen=True)
class Comparison:
    deltas: tuple[MonthDelta, ...]
    drivers: tuple[Driver, ...]
