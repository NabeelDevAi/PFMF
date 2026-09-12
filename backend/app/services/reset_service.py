"""DELETE /me/data (RFP §4.8, architecture §9). Resets a user's data
without deleting the account -- that's a distinct, separate operation
(account deletion, screen-flow F9) not covered by this endpoint or built
yet; see claude_docs/backend-plan/12-open-questions-and-future-hardening.md.

Scope of "reset", a call made here since neither locked doc spells out
the exact boundary between reset and delete-account:

- Every derived scenario is deleted outright (cascades take their
  transactions and overlays with them).
- Base itself is NEVER deleted -- that would contradict the
  scenario.base_immutable rule enforced everywhere else in this
  codebase, and a user needs *some* scenario to land on afterward, so
  making an exception here would replace one invariant with a special
  case. Base's own transactions are cleared instead.
- User-created categories are deleted (system categories are global
  reference data, untouched).
- opening_balance_minor and opening_balance_date reset to the same
  defaults a fresh registration gets (0, today) -- this is financial
  state, the anchor for a plan that no longer exists.
- currency_code, locale, and display_name are left untouched: account
  preferences, not "data" in the RFP §4.8 sense of the word.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.api.errors import APIError
from app.repositories.category_repository import CategoryRepository
from app.repositories.scenario_repository import ScenarioRepository
from app.repositories.transaction_repository import TransactionRepository
from app.repositories.user_settings_repository import UserSettingsRepository


class ResetService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = UserSettingsRepository(db)
        self.categories = CategoryRepository(db)
        self.scenarios = ScenarioRepository(db)
        self.transactions = TransactionRepository(db)

    def reset(self, user_id: uuid.UUID) -> None:
        settings = self.settings.get_by_user_id(user_id)
        base = self.scenarios.get_base(user_id)
        if settings is None or base is None:
            raise APIError("resource.not_found")

        self.scenarios.delete_all_non_base_for_user(user_id)
        self.transactions.delete_all_for_scenario(user_id, base.id)
        self.categories.delete_all_owned_by_user(user_id)

        settings.opening_balance_minor = 0
        settings.opening_balance_date = date.today()
        self.settings.save(settings)
