"""Application configuration.

Environment-driven settings (see claude_docs/backend-plan/02-configuration-and-environment.md).
Nothing secret is hardcoded here. Locally these come from backend/.env (gitignored);
`.env.example` documents the required shape.

Required settings have no default, so instantiating Settings() fails fast if
they're missing -- this is deliberate, not an oversight.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["local", "staging", "production"] = "local"

    # Required, no default -- startup fails fast if missing.
    database_url: str
    jwt_secret: SecretStr

    # Only needed to run the test suite / connectivity check locally.
    test_database_url: str | None = None

    jwt_access_ttl_minutes: int = 15
    jwt_refresh_ttl_days: int = 30
    cors_origins: list[str] = []
    log_level: str = "INFO"
    max_horizon_months: int = 120
    # Hard backstop on PUT /me/balance's as-of date (balance.as_of_too_old).
    # Distinct from the dashboard's stale-balance *prompt* threshold (a soft
    # UX nudge, proposed at 30 days in screen-flow §5.1/§14 -- unrelated,
    # client-side only, no backend setting). Product decision, not derived
    # from either locked doc.
    balance_as_of_max_age_years: int = 5

    # Rate limiting (in-memory for this build -- see backend-plan/07 §6).
    rate_limit_auth_attempts_per_minute: int = 5

    # Profile avatar storage -- local disk for this build, explicitly
    # acknowledged as throwaway infrastructure (see
    # 12-open-questions-and-future-hardening.md): most real hosting has an
    # ephemeral or non-shared filesystem, so this moves to real object
    # storage the moment deployment is picked. Relative to the backend/
    # working directory unless an absolute path is set.
    media_root: Path = Path("media")
    avatar_max_bytes: int = 5 * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    """Cached so Settings() -- and its env parsing / fail-fast validation --
    runs once per process, not on every call site."""
    return Settings()
