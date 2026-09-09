from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.schemas.me import MeOut, SettingsPatch
from app.db.models.user import User
from app.db.session import get_db
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
