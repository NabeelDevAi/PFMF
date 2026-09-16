from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.schemas.auth import ChangePasswordRequest
from app.api.schemas.common import ActionResult
from app.api.schemas.export import ExportOut, export_to_csv_zip
from app.api.schemas.me import BalanceUpdate, MeOut, SettingsPatch
from app.db.models.user import User
from app.db.session import get_db
from app.services.account_service import AccountService
from app.services.auth_service import AuthService
from app.services.export_service import ExportService
from app.services.reset_service import ResetService
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/me", tags=["me"])


@router.get("", response_model=MeOut)
def get_me(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> MeOut:
    settings = SettingsService(db).get(user.id)
    return MeOut.model_validate(
        {"id": user.id, "email": user.email, "created_at": user.created_at, "settings": settings}
    )


@router.patch("/settings", response_model=MeOut)
def patch_settings(
    body: SettingsPatch, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> MeOut:
    settings = SettingsService(db).patch(user.id, **body.model_dump(exclude_unset=True))
    db.commit()
    return MeOut.model_validate(
        {"id": user.id, "email": user.email, "created_at": user.created_at, "settings": settings}
    )


@router.put("/balance", response_model=MeOut)
def update_balance(
    body: BalanceUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> MeOut:
    """The only write path for the Current Cash Balance (D-04, architecture
    §9.1) -- deliberately separate from PATCH /me/settings so this
    endpoint's consequence (every forecast in every scenario re-anchors)
    stays visible in the API, the logs, and the client code."""
    settings = SettingsService(db).update_balance(
        user.id,
        current_balance_minor=body.current_balance_minor,
        balance_as_of=body.balance_as_of,
    )
    db.commit()
    return MeOut.model_validate(
        {"id": user.id, "email": user.email, "created_at": user.created_at, "settings": settings}
    )


@router.patch("/password", response_model=ActionResult)
def change_password(
    body: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ActionResult:
    """The only way to change a password in Phase 1 -- no forgot/reset-
    password-via-email flow (see auth_service.py's module docstring).
    Revokes every other session; the client should expect to
    re-authenticate afterward."""
    AuthService(db).change_password(
        user.id, current_password=body.current_password, new_password=body.new_password
    )
    db.commit()
    return ActionResult.from_key("auth.password_changed")


@router.get("/export", response_model=None)
def export_data(
    format: Literal["json", "csv"] = Query("json"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExportOut | Response:
    """Same raw, reconstructable-backup data either way (RFP §4.8) --
    `format` just picks the serialization. `csv` bundles five CSV files
    (one per table: account, categories, scenarios, transactions,
    overlays) as a ZIP, since a single flat CSV can't hold five
    differently-shaped tables. Defaults to `json` for backward
    compatibility; the client is expected to always pass this
    explicitly rather than rely on the default."""
    data = ExportService(db).export(user.id)
    if format == "csv":
        return Response(
            content=export_to_csv_zip(data),
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=export.zip"},
        )
    return ExportOut.from_data(data)


@router.delete("/data", response_model=ActionResult)
def reset_data(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ActionResult:
    ResetService(db).reset(user.id)
    db.commit()
    return ActionResult.from_key("me.data_reset")


@router.delete("", response_model=ActionResult)
def delete_account(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ActionResult:
    AccountService(db).delete_account(user.id)
    db.commit()
    return ActionResult.from_key("me.account_deleted")
