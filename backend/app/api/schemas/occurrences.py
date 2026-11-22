from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel

from app.domain.enums import Direction, Origin, Recurrence
from app.services.occurrence_service import MonthOccurrences


class MonthOccurrenceOut(BaseModel):
    """One dated instance in the month. `on` is this occurrence's own due
    date, never the series start date; `start_date`/`end_date` describe the
    series it belongs to. `transaction_id` is the id of the rule it came from
    (the same `id` `GET /scenarios/{id}/transactions` returns), which is what
    an edit screen opens. Amounts are positive minor units with the sign in
    `direction` (D-10)."""

    transaction_id: uuid.UUID
    name: str
    direction: Direction
    amount_minor: int
    on: date
    origin: Origin
    recurrence: Recurrence
    start_date: date
    end_date: date | None
    category_id: uuid.UUID | None


class MonthTotalsOut(BaseModel):
    income_minor: int
    expense_minor: int
    net_minor: int


class MonthOccurrencesOut(BaseModel):
    scenario_id: uuid.UUID
    month: str  # "YYYY-MM"
    currency_code: str
    items: list[MonthOccurrenceOut]
    totals: MonthTotalsOut

    @classmethod
    def from_result(cls, result: MonthOccurrences) -> MonthOccurrencesOut:
        items = [
            MonthOccurrenceOut(
                transaction_id=uuid.UUID(i.occurrence.transaction_id),
                name=i.occurrence.name,
                direction=Direction(i.occurrence.direction.value),
                amount_minor=i.occurrence.amount_minor,
                on=i.occurrence.on,
                origin=Origin(i.transaction.origin.value),
                recurrence=Recurrence(i.transaction.recurrence.value),
                start_date=i.transaction.start_date,
                end_date=i.transaction.end_date,
                category_id=(
                    uuid.UUID(i.transaction.category_id) if i.transaction.category_id else None
                ),
            )
            for i in result.items
        ]
        return cls(
            scenario_id=result.scenario_id,
            month=str(result.month),
            currency_code=result.currency_code,
            items=items,
            totals=MonthTotalsOut(
                income_minor=result.income_minor,
                expense_minor=result.expense_minor,
                net_minor=result.net_minor,
            ),
        )
