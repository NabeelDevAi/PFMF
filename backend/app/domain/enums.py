"""Persistence/API-facing vocabulary.

Deliberately independent of app.engine.types even though the values are
identical strings: the DB schema's enum values have their own migration
lifecycle (a Postgres ENUM type, locked in by a migration) and shouldn't be
coupled to the engine's own vocabulary module, which is free to evolve on
its own terms. Services are the layer that translates between the two when
building ResolvedTransaction objects for the engine.
"""

from enum import StrEnum


class Direction(StrEnum):
    INCOME = "income"
    EXPENSE = "expense"


class Recurrence(StrEnum):
    """The frozen recurrence set (D-08)."""

    ONE_TIME = "one_time"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMIANNUAL = "semiannual"
    ANNUAL = "annual"


class OverlayOp(StrEnum):
    EXCLUDE = "exclude"
    OVERRIDE = "override"


class Origin(StrEnum):
    """How a transaction relates to Base in a resolved scenario view
    (architecture §6, §9.2). Never stored -- computed at read time by
    ScenarioResolver.

    EXCLUDED has no engine-side counterpart (app.engine.types.Origin) --
    an excluded row is never fed to the engine at all, so it only exists
    at this API/domain layer, for the "removed from this plan" view
    (GET .../transactions?filter=removed|all)."""

    OWN = "own"
    INHERITED = "inherited"
    OVERRIDDEN = "overridden"
    ADDED = "added"
    EXCLUDED = "excluded"


class DriverChange(StrEnum):
    """How a comparison driver's contribution came about, between ledger A
    and ledger B (architecture §8). Never stored -- computed at compare
    time. Mirrors app.engine.types.DriverChange for the same
    independent-vocabulary reason as the rest of this module."""

    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
