"""Password hashing, JWT access tokens, and opaque refresh-token generation.

None of this is the engine -- it's fine for this module to read the clock
and touch secrets. What it must never do is let a raw password or a raw
refresh token reach a log line.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError

from app.core.config import get_settings

_hasher = PasswordHasher()


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(password_hash: str, plain: str) -> bool:
    try:
        return _hasher.verify(password_hash, plain)
    except (VerifyMismatchError, VerificationError):
        return False


def encode_access_token(user_id: uuid.UUID) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_access_ttl_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret.get_secret_value(), algorithm="HS256")


def decode_access_token(token: str) -> dict:
    """Raises jwt.PyJWTError (or a subclass) on any invalid/expired token --
    callers map that to the auth.token_* error codes, not this module."""
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret.get_secret_value(), algorithms=["HS256"])


def generate_refresh_token() -> str:
    """The raw, opaque token sent to the client. Never stored as-is."""
    return secrets.token_urlsafe(48)


def hash_token(raw: str) -> str:
    """One-way hash for anything stored server-side that must match a raw
    value presented later (refresh tokens). Not a password hash -- these
    values are already high-entropy random tokens, so a fast,
    deterministic hash (for exact-match lookup) is correct here; Argon2
    is for low-entropy human passwords, not this."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
