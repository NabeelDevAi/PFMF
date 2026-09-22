"""Exclude or override a Base transaction from within a derived scenario.
This is the API surface behind architecture §9.2's critical rule: editing
an inherited/overridden row goes through these routes, never a direct
PATCH/DELETE on /transactions/{id} (app/api/v1/transactions.py). The
backend can't stop a client from calling the wrong endpoint -- it can
only guarantee the *result* is safe either way (an overlay can never
target anything but a Base transaction, and Base is never mutated from
here), which is exactly what overlay_service.py enforces.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.schemas.common import ActionResult
from app.api.schemas.overlays import OverlayCreate, OverlayOut, OverlayPatch
from app.db.models.user import User
from app.db.session import get_db
from app.services.overlay_service import OverlayService

router = APIRouter(prefix="/scenarios", tags=["overlays"])


@router.post(
    "/{scenario_id}/overlays", response_model=OverlayOut, status_code=status.HTTP_201_CREATED
)
def create_overlay(
    scenario_id: uuid.UUID,
    body: OverlayCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OverlayOut:
    overlay = OverlayService(db).create(
        user.id,
        scenario_id,
        base_transaction_id=body.base_transaction_id,
        op=body.op,
        ovr_name=body.ovr_name,
        ovr_amount_minor=body.ovr_amount_minor,
        ovr_category_id=body.ovr_category_id,
        ovr_recurrence=body.ovr_recurrence,
        ovr_start_date=body.ovr_start_date,
        ovr_end_date=body.ovr_end_date,
        unset_end_date=body.unset_end_date,
    )
    db.commit()
    return OverlayOut.model_validate(overlay)


@router.patch("/{scenario_id}/overlays/{overlay_id}", response_model=OverlayOut)
def patch_overlay(
    scenario_id: uuid.UUID,
    overlay_id: uuid.UUID,
    body: OverlayPatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OverlayOut:
    overlay = OverlayService(db).update(
        user.id,
        scenario_id,
        overlay_id,
        ovr_name=body.ovr_name,
        ovr_amount_minor=body.ovr_amount_minor,
        ovr_category_id=body.ovr_category_id,
        _unset_category_id=body.unset_category_id,
        ovr_recurrence=body.ovr_recurrence,
        ovr_start_date=body.ovr_start_date,
        ovr_end_date=body.ovr_end_date,
        unset_end_date=body.unset_end_date,
    )
    db.commit()
    return OverlayOut.model_validate(overlay)


@router.delete("/{scenario_id}/overlays/{overlay_id}", response_model=ActionResult)
def delete_overlay(
    scenario_id: uuid.UUID,
    overlay_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ActionResult:
    OverlayService(db).delete(user.id, scenario_id, overlay_id)
    db.commit()
    return ActionResult.from_key("overlay.deleted")
