"""The engine's closed vocabulary.

Pure. No imports from outside the standard library. Every other module in
app/engine/ builds on these types and nothing else.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

# Money is ALWAYS integer minor units (halalas/cents). Never float, never
# Decimal, even transiently. This alias exists so every signature that
# carries money says so explicitly.
Minor = int


class Direction(StrEnum):
    INCOME = "income"
    EXPENSE = "expense"


class Recurrence(StrEnum):
    """The frozen recurrence set. No custom cron-style rules -- ever."""

    ONE_TIME = "one_time"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMIANNUAL = "semiannual"
    ANNUAL = "annual"


class Origin(StrEnum):
    """How a resolved transaction relates to Base. Set by the scenario
    resolver (a service, outside the engine) before the engine ever sees a
    transaction -- the engine only carries this tag through to occurrences
    and comparison drivers, it never assigns or interprets it."""

    OWN = "own"  # Base's own transactions
    INHERITED = "inherited"  # unmodified, inherited from Base
    OVERRIDDEN = "overridden"  # a Base transaction, overlaid in this scenario
    ADDED = "added"  # local to this scenario


class DriverChange(StrEnum):
    """How a comparison driver's contribution came about, between ledger A
    and ledger B. See compare.py."""

    ADDED = "added"  # present only in B
    REMOVED = "removed"  # present only in A
    MODIFIED = "modified"  # present in both, signed total differs


@dataclass(frozen=True, order=True)
class YearMonth:
    """An orderable, hashable calendar month. All month keys crossing the
    API boundary are str(YearMonth) ("YYYY-MM"). The engine never derives
    one of these from a clock -- it is always handed in."""

    year: int
    month: int

    def __post_init__(self) -> None:
        if not 1 <= self.month <= 12:
            raise ValueError(f"month must be 1-12, got {self.month}")

    @classmethod
    def from_date(cls, d: date) -> YearMonth:
        return cls(d.year, d.month)

    @classmethod
    def parse(cls, s: str) -> YearMonth:
        """Parse "YYYY-MM"."""
        y, m = s.split("-")
        return cls(int(y), int(m))

    def add(self, months: int) -> YearMonth:
        """This month plus `months` (may be negative)."""
        idx = self.year * 12 + (self.month - 1) + months
        return YearMonth(idx // 12, idx % 12 + 1)

    def months_until(self, other: YearMonth) -> int:
        """Number of months from this month to `other` (may be negative)."""
        return (other.year * 12 + other.month) - (self.year * 12 + self.month)

    def first_day(self) -> date:
        return date(self.year, self.month, 1)

    def __str__(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"
