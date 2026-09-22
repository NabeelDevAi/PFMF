"""FastAPI dependencies wrapping the in-memory rate limiter (backend-plan/07
§6) for the specific routes that need it. Kept separate from app/core/rate_limit.py
so the limiter itself stays framework-agnostic."""

from __future__ import annotations

from fastapi import Request

from app.core.config import get_settings
from app.core.errors import APIError
from app.core.rate_limit import limiter


def rate_limit_by_ip(request: Request) -> None:
    """5/min per IP on login and register (the default threshold)."""
    settings = get_settings()
    key = f"ip:{request.client.host if request.client else 'unknown'}:{request.url.path}"
    if not limiter.hit(
        key, max_attempts=settings.rate_limit_auth_attempts_per_minute, window_seconds=60
    ):
        raise APIError("rate_limited")
