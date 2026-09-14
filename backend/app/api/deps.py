"""Shared FastAPI dependencies: the DB session and the current-user
extraction from a bearer access token. Auth and validation only -- no
business logic lives here (backend-plan/07 §1)."""

from __future__ import annotations

import uuid

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.core.security import decode_access_token
from app.db.models.user import User
from app.db.session import get_db
from app.repositories.user_repository import UserRepository

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise APIError("auth.token_invalid")

    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise APIError("auth.token_expired") from None
    except jwt.PyJWTError:
        raise APIError("auth.token_invalid") from None

    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        raise APIError("auth.token_invalid") from None

    user = UserRepository(db).get_by_id(user_id)
    if user is None:
        # The user this token names no longer exists (e.g. account deleted).
        raise APIError("auth.token_invalid")
    return user
