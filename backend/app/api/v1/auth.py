from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.rate_limit_deps import rate_limit_by_ip
from app.api.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPairResponse,
)
from app.api.schemas.common import ActionResult
from app.db.session import get_db
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenPairResponse, status_code=status.HTTP_201_CREATED)
def register(
    body: RegisterRequest, db: Session = Depends(get_db), _rl: None = Depends(rate_limit_by_ip)
) -> TokenPairResponse:
    tokens = AuthService(db).register(email=body.email, password=body.password, name=body.name)
    db.commit()
    return TokenPairResponse(access_token=tokens.access_token, refresh_token=tokens.refresh_token)


@router.post("/login", response_model=TokenPairResponse)
def login(
    body: LoginRequest, db: Session = Depends(get_db), _rl: None = Depends(rate_limit_by_ip)
) -> TokenPairResponse:
    tokens = AuthService(db).login(email=body.email, password=body.password)
    db.commit()
    return TokenPairResponse(access_token=tokens.access_token, refresh_token=tokens.refresh_token)


@router.post("/refresh", response_model=TokenPairResponse)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)) -> TokenPairResponse:
    tokens = AuthService(db).refresh(refresh_token=body.refresh_token)
    db.commit()
    return TokenPairResponse(access_token=tokens.access_token, refresh_token=tokens.refresh_token)


@router.post("/logout", response_model=ActionResult)
def logout(body: LogoutRequest, db: Session = Depends(get_db)) -> ActionResult:
    AuthService(db).logout(refresh_token=body.refresh_token)
    db.commit()
    return ActionResult.from_key("auth.logged_out")
