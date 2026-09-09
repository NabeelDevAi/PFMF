"""FastAPI dependencies wrapping the in-memory rate limiter (backend-plan/07
§6) for the specific routes that need it. Kept separate from app/core/rate_limit.py
so the limiter itself stays framework-agnostic."""

from __future__ import annotations

from fastapi import Request

from app.api.errors import APIError
from app.core.config import get_settings
from app.core.rate_limit import limiter


def rate_limit_by_ip(request: Request) -> None:
    """5/min per IP on login and register (the default threshold)."""
    settings = get_settings()
    key = f"ip:{request.client.host if request.client else 'unknown'}:{request.url.path}"
    if not limiter.hit(
        key, max_attempts=settings.rate_limit_auth_attempts_per_minute, window_seconds=60
    ):
        raise APIError("rate_limited")


def rate_limit_password_reset_by_email(email: str) -> None:
    """3/hour per email on password-reset requests. Called directly from
    the route (not as a Depends) since the key depends on the request body,
    which Depends can't see before the route itself parses it."""
    settings = get_settings()
    key = f"reset:{email.lower()}"
    if not limiter.hit(
        key, max_attempts=settings.rate_limit_password_reset_attempts_per_hour, window_seconds=3600
    ):
        raise APIError("rate_limited")
