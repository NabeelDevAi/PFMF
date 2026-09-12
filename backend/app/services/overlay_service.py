"""Overlay create/patch/delete: exclude or override a Base transaction
from within a derived scenario. See architecture §5, §6, §9.2 and
backend-plan/06-services-module.md.

`op` is fixed at creation -- PATCH only ever touches the ovr_* fields,
never flips exclude <-> override. Matches how the screen-flow spec
describes the editing model: "Remove from this plan" and overriding a
value are distinct user actions, not the same overlay reinterpreted.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.api.errors import APIError
from app.db.models.scenario_overlay import ScenarioOverlay
from app.db.models.transaction import Transaction
from app.domain.enums import OverlayOp, Recurrence
from app.repositories.category_repository import CategoryRepository
from app.repositories.overlay_repository import OverlayRepository
from app.repositories.scenario_repository import ScenarioRepository
from app.repositories.transaction_repository import TransactionRepository


class OverlayService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.scenarios = ScenarioRepository(db)
        self.transactions = TransactionRepository(db)
        self.overlays = OverlayRepository(db)
        self.categories = CategoryRepository(db)

    def create(
        self,
        user_id: uuid.UUID,
        scenario_id: uuid.UUID,
        *,
        base_transaction_id: uuid.UUID,
        op: OverlayOp,
        ovr_name: str | None = None,
        ovr_amount_minor: int | None = None,
        ovr_category_id: uuid.UUID | None = None,
        ovr_recurrence: Recurrence | None = None,
        ovr_start_date: date | None = None,
        ovr_end_date: date | None = None,
        unset_end_date: bool = False,
    ) -> ScenarioOverlay:
        self._get_non_base_scenario(user_id, scenario_id)
        target = self._get_base_transaction(user_id, base_transaction_id)

        if self.overlays.get_by_target(scenario_id, base_transaction_id) is not None:
            raise APIError("overlay.already_exists")

        if op is OverlayOp.OVERRIDE:
            merged = _merge(
                target,
                ovr_amount_minor=ovr_amount_minor,
                ovr_recurrence=ovr_recurrence,
                ovr_start_date=ovr_start_date,
                ovr_end_date=ovr_end_date,
                unset_end_date=unset_end_date,
            )
            _validate_merged(merged)
            if ovr_category_id is not None:
                self._check_category(user_id, ovr_category_id)

        return self.overlays.create(
            scenario_id=scenario_id,
            base_transaction_id=base_transaction_id,
            op=op,
            ovr_name=ovr_name,
            ovr_amount_minor=ovr_amount_minor,
            ovr_category_id=ovr_category_id,
            ovr_recurrence=ovr_recurrence,
            ovr_start_date=ovr_start_date,
            ovr_end_date=ovr_end_date,
            unset_end_date=unset_end_date,
        )

    def update(
        self,
        user_id: uuid.UUID,
        scenario_id: uuid.UUID,
        overlay_id: uuid.UUID,
        *,
        ovr_name: str | None = None,
        ovr_amount_minor: int | None = None,
        ovr_category_id: uuid.UUID | None = None,
        _unset_category_id: bool = False,
        ovr_recurrence: Recurrence | None = None,
        ovr_start_date: date | None = None,
        ovr_end_date: date | None = None,
        unset_end_date: bool | None = None,
    ) -> ScenarioOverlay:
        self._get_scenario(user_id, scenario_id)
        overlay = self.overlays.get_by_id(scenario_id, overlay_id)
        if overlay is None:
            raise APIError("resource.not_found")

        if ovr_name is not None:
            overlay.ovr_name = ovr_name
        if ovr_amount_minor is not None:
            overlay.ovr_amount_minor = ovr_amount_minor
        if _unset_category_id:
            overlay.ovr_category_id = None
        elif ovr_category_id is not None:
            self._check_category(user_id, ovr_category_id)
            overlay.ovr_category_id = ovr_category_id
        if ovr_recurrence is not None:
            overlay.ovr_recurrence = ovr_recurrence
        if ovr_start_date is not None:
            overlay.ovr_start_date = ovr_start_date

        # unset_end_date wins over a simultaneously-supplied ovr_end_date --
        # an explicit "make it open-ended" beats a stale date in the same body.
        if unset_end_date is True:
            overlay.unset_end_date = True
            overlay.ovr_end_date = None
        elif ovr_end_date is not None:
            overlay.unset_end_date = False
            overlay.ovr_end_date = ovr_end_date
        elif unset_end_date is False:
            overlay.unset_end_date = False

        if overlay.op is OverlayOp.OVERRIDE:
            target = self.transactions.get_by_id(user_id, overlay.base_transaction_id)
            merged = _merge(
                target,
                ovr_amount_minor=overlay.ovr_amount_minor,
                ovr_recurrence=overlay.ovr_recurrence,
                ovr_start_date=overlay.ovr_start_date,
                ovr_end_date=overlay.ovr_end_date,
                unset_end_date=overlay.unset_end_date,
            )
            _validate_merged(merged)

        self.overlays.save(overlay)
        return overlay

    def delete(self, user_id: uuid.UUID, scenario_id: uuid.UUID, overlay_id: uuid.UUID) -> None:
        self._get_scenario(user_id, scenario_id)
        overlay = self.overlays.get_by_id(scenario_id, overlay_id)
        if overlay is None:
            raise APIError("resource.not_found")
        self.overlays.delete(overlay)

    def _get_scenario(self, user_id: uuid.UUID, scenario_id: uuid.UUID):
        scenario = self.scenarios.get_by_id(user_id, scenario_id)
        if scenario is None:
            raise APIError("resource.not_found")
        return scenario

    def _get_non_base_scenario(self, user_id: uuid.UUID, scenario_id: uuid.UUID):
        scenario = self._get_scenario(user_id, scenario_id)
        if scenario.is_base:
            raise APIError("overlay.scenario_is_base")
        return scenario

    def _get_base_transaction(
        self, user_id: uuid.UUID, base_transaction_id: uuid.UUID
    ) -> Transaction:
        base = self.scenarios.get_base(user_id)
        target = self.transactions.get_by_id(user_id, base_transaction_id)
        if base is None or target is None or target.scenario_id != base.id:
            raise APIError("overlay.target_not_in_base")
        return target

    def _check_category(self, user_id: uuid.UUID, category_id: uuid.UUID) -> None:
        if self.categories.get_visible_to_user(user_id, category_id) is None:
            raise APIError("validation.invalid", {"field": "ovr_category_id"})


def _merge(
    target: Transaction,
    *,
    ovr_amount_minor: int | None,
    ovr_recurrence: Recurrence | None,
    ovr_start_date: date | None,
    ovr_end_date: date | None,
    unset_end_date: bool,
) -> dict:
    return {
        "amount_minor": ovr_amount_minor if ovr_amount_minor is not None else target.amount_minor,
        "recurrence": ovr_recurrence if ovr_recurrence is not None else target.recurrence,
        "start_date": ovr_start_date if ovr_start_date is not None else target.start_date,
        "end_date": None
        if unset_end_date
        else (ovr_end_date if ovr_end_date is not None else target.end_date),
    }


def _validate_merged(merged: dict) -> None:
    if merged["amount_minor"] <= 0:
        raise APIError("transaction.amount_not_positive", {"field": "ovr_amount_minor"})
    if merged["end_date"] is not None and merged["end_date"] < merged["start_date"]:
        raise APIError("transaction.end_before_start", {"field": "ovr_end_date"})
    if merged["recurrence"] is Recurrence.ONE_TIME and merged["end_date"] is not None:
        raise APIError("transaction.one_time_has_end_date", {"field": "ovr_end_date"})
