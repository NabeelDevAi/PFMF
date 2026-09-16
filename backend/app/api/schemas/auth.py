from __future__ import annotations

from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    """PATCH /me/password -- the only way to change a password in Phase 1
    (no forgot/reset-password-via-email flow; see auth_service.py's
    module docstring). current_password is required, never optional --
    a bare new-password field would let a hijacked-but-still-logged-in
    session lock the real owner out."""

    current_password: str
    new_password: str


class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
