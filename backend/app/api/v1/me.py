from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.schemas.export import ExportOut
from app.api.schemas.me import MeOut, SettingsPatch
from app.db.models.user import User
from app.db.session import get_db
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


@router.get("/export", response_model=ExportOut)
def export_data(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ExportOut:
    data = ExportService(db).export(user.id)
    return ExportOut.from_data(data)


@router.delete("/data", status_code=status.HTTP_204_NO_CONTENT)
def reset_data(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> None:
    ResetService(db).reset(user.id)
    db.commit()
