from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.schemas.common import ActionResult
from app.api.schemas.export import ExportOut
from app.api.schemas.me import BalanceUpdate, MeOut, SettingsPatch
from app.db.models.user import User
from app.db.session import get_db
from app.services.account_service import AccountService
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


@router.get("/export", response_model=ExportOut)
def export_data(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ExportOut:
    data = ExportService(db).export(user.id)
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
