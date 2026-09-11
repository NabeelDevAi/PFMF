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
    """Not consumed until the scenario_overlays table lands in milestone M4."""

    EXCLUDE = "exclude"
    OVERRIDE = "override"


class Origin(StrEnum):
    """How a transaction relates to Base in a resolved scenario view
    (architecture §6, §9.2). Never stored -- computed at read time by
    whatever currently does resolution.

    Milestone M3 only ever produces OWN (Base's own rows) or ADDED (a
    derived scenario's own local rows), since there's no overlay support
    yet to produce INHERITED or OVERRIDDEN -- a non-base scenario simply
    doesn't show Base's transactions until the real resolver lands in M4.
    """

    OWN = "own"
    INHERITED = "inherited"
    OVERRIDDEN = "overridden"
    ADDED = "added"
