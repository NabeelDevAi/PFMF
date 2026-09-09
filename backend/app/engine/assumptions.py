"""The Phase 2 seam. Inert in Phase 1 -- built and wired into the pipeline
now specifically so the pipeline's shape doesn't change when Phase 2 adds
inflation / salary growth. The signature here is the signature Phase 2
extends, which is what makes "no engine rebuild" a verifiable claim.

Rounding policy for Phase 2 (not implemented here, recorded for when it is):
half-even, applied at the occurrence level, never at the aggregate level --
aggregate-level rounding is how a ledger stops reconciling.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import Occurrence


@dataclass(frozen=True)
class Assumptions:
    """Empty in Phase 1. Phase 2 adds growth-rate fields here."""

    @classmethod
    def none(cls) -> Assumptions:
        return cls()


def apply_assumptions(occurrences: list[Occurrence], assumptions: Assumptions) -> list[Occurrence]:
    """No-op in Phase 1."""
    return occurrences
