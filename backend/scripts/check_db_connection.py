"""One-off connectivity check for the foundation milestone.

Confirms both the dev database and the test database (if configured) are
reachable with the current settings, without needing the full app or pytest.

Run from backend/:
    python -m scripts.check_db_connection
"""

from __future__ import annotations

from sqlalchemy import create_engine, text

from app.core.config import get_settings


def _check(url: str, label: str) -> None:
    engine = create_engine(url)
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    engine.dispose()
    print(f"[OK]   {label} reachable")


def main() -> None:
    settings = get_settings()
    _check(settings.database_url, "dev database  (DATABASE_URL)")
    if settings.test_database_url:
        _check(settings.test_database_url, "test database (TEST_DATABASE_URL)")
    else:
        print("[SKIP] TEST_DATABASE_URL not set")


if __name__ == "__main__":
    main()
