"""One calendar month of a plan's dated occurrences (UAT-007).

Expands every resolved transaction of the plan over that single month with
the same engine `expand` the forecast uses, so the month's totals always
equal the forecast's row for that month. Pure arithmetic over the resolver's
output: no new financial rules.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import APIError
from app.engine.expand import expand
from app.engine.models import Occurrence, ResolvedTransaction
from app.engine.types import Direction, YearMonth
from app.repositories.scenario_repository import ScenarioRepository
from app.services.scenario_resolver import ScenarioResolver
from app.services.settings_service import SettingsService


@dataclass(frozen=True)
class MonthOccurrence:
    occurrence: Occurrence
    transaction: ResolvedTransaction


@dataclass(frozen=True)
class MonthOccurrences:
    scenario_id: uuid.UUID
    month: YearMonth
    currency_code: str
    items: list[MonthOccurrence]
    income_minor: int
    expense_minor: int

    @property
    def net_minor(self) -> int:
        return self.income_minor - self.expense_minor


class OccurrenceService:
    def __init__(self, db: Session) -> None:
        self.scenarios = ScenarioRepository(db)
        self.settings = SettingsService(db)
        self.resolver = ScenarioResolver(db)

    def month(
        self, user_id: uuid.UUID, scenario_id: uuid.UUID, month: YearMonth
    ) -> MonthOccurrences:
        scenario = self.scenarios.get_by_id(user_id, scenario_id)
        if scenario is None:
            raise APIError("resource.not_found")
        settings = self.settings.get(user_id)

        # Months may be browsed in both directions, but not without limit:
        # the same span the forecast allows, either side of the balance month.
        anchor = YearMonth.from_date(settings.balance_as_of)
        if abs(anchor.months_until(month)) > get_settings().max_horizon_months:
            raise APIError("validation.invalid", {"field": "month"})

        resolved = self.resolver.resolve(user_id, scenario)
        by_id = {t.id: t for t in resolved}
        start, end = month.first_day(), month.last_day()

        items: list[MonthOccurrence] = []
        for txn in resolved:
            for occ in expand(txn, start, end):
                items.append(MonthOccurrence(occ, by_id[occ.transaction_id]))
        items.sort(key=lambda i: (i.occurrence.on, i.occurrence.name, i.occurrence.transaction_id))

        income = sum(
            i.occurrence.amount_minor for i in items if i.occurrence.direction is Direction.INCOME
        )
        expense = sum(
            i.occurrence.amount_minor for i in items if i.occurrence.direction is Direction.EXPENSE
        )
        return MonthOccurrences(
            scenario_id=scenario.id,
            month=month,
            currency_code=settings.currency_code,
            items=items,
            income_minor=income,
            expense_minor=expense,
        )
