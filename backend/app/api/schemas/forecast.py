"""Response shapes for GET /scenarios/{id}/forecast and GET /forecast/compare.

Matches architecture §7.5's output shape exactly: raw integers, ISO month
keys, no formatted strings, no currency symbols -- the client formats
(architecture §10). This one payload shape feeds the dashboard, all three
forecast chart views, the monthly table, and month breakdown (§9.1) --
there is no separate endpoint for any of those.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import TYPE_CHECKING

from pydantic import BaseModel

from app.domain.enums import Direction, DriverChange

if TYPE_CHECKING:
    from app.services.compare_service import CompareResult
    from app.services.forecast_service import ForecastResult


class MonthRowOut(BaseModel):
    month: str  # "YYYY-MM"
    income_minor: int
    expense_minor: int
    net_minor: int
    closing_balance_minor: int


class TotalsOut(BaseModel):
    income_minor: int
    expense_minor: int
    net_minor: int
    closing_balance_minor: int


class ForecastOut(BaseModel):
    scenario_id: uuid.UUID
    anchor_month: str
    balance_as_of: date
    horizon_months: int
    currency_code: str
    current_balance_minor: int
    current_month: str  # where "today" sits in `months` (architecture §7.5)
    months_elapsed: int  # anchor_month -> current_month, in months
    months: list[MonthRowOut]
    totals: TotalsOut

    @classmethod
    def from_result(cls, result: ForecastResult) -> ForecastOut:
        ledger = result.ledger
        months = [
            MonthRowOut(
                month=str(row.month),
                income_minor=row.income_minor,
                expense_minor=row.expense_minor,
                net_minor=row.net_minor,
                closing_balance_minor=row.closing_balance_minor,
            )
            for row in ledger.months
        ]
        totals = TotalsOut(
            income_minor=sum(row.income_minor for row in ledger.months),
            expense_minor=sum(row.expense_minor for row in ledger.months),
            net_minor=sum(row.net_minor for row in ledger.months),
            closing_balance_minor=ledger.months[-1].closing_balance_minor,
        )
        return cls(
            scenario_id=result.scenario_id,
            anchor_month=str(ledger.anchor_month),
            balance_as_of=result.balance_as_of,
            horizon_months=ledger.horizon_months,
            currency_code=result.currency_code,
            current_balance_minor=ledger.current_balance_minor,
            current_month=str(result.current_month),
            months_elapsed=result.months_elapsed,
            months=months,
            totals=totals,
        )


class MonthDeltaOut(BaseModel):
    month: str
    net_delta_minor: int
    closing_balance_delta_minor: int
    closing_balance_delta_pct: float | None  # None (never 0 or inf) when A's value is 0


class DriverOut(BaseModel):
    source_id: str
    name: str
    direction: Direction
    change: DriverChange
    base_total_minor: int
    scenario_total_minor: int
    total_contribution_minor: int
    active_months: int


class CompareOut(BaseModel):
    a: ForecastOut
    b: ForecastOut
    deltas: list[MonthDeltaOut]
    drivers: list[DriverOut]

    @classmethod
    def from_result(cls, result: CompareResult) -> CompareOut:
        deltas = [
            MonthDeltaOut(
                month=str(d.month),
                net_delta_minor=d.net_delta_minor,
                closing_balance_delta_minor=d.closing_balance_delta_minor,
                closing_balance_delta_pct=d.closing_balance_delta_pct,
            )
            for d in result.comparison.deltas
        ]
        drivers = [
            DriverOut(
                source_id=d.source_id,
                name=d.name,
                direction=Direction(d.direction.value),
                change=DriverChange(d.change.value),
                base_total_minor=d.base_total_minor,
                scenario_total_minor=d.scenario_total_minor,
                total_contribution_minor=d.total_contribution_minor,
                active_months=d.active_months,
            )
            for d in result.comparison.drivers
        ]
        return cls(
            a=ForecastOut.from_result(result.a),
            b=ForecastOut.from_result(result.b),
            deltas=deltas,
            drivers=drivers,
        )
