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
    """The frozen recurrence set (D-08). Not consumed by any table until
    the transactions table lands in milestone M3 -- defined now because the
    architecture doc's DDL declares all three enum types together."""

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
