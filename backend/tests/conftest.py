"""Shared fixtures for repository/service/API tests -- everything that
needs the dedicated local Postgres test database (backend-plan/10 §5).
Engine-level tests (tests/engine/) request none of these fixtures, so
nothing here ever runs for them -- no migrations, no DB connection at all,
matching the "engine tests need no infrastructure" principle.

Migrations run once per test session, shelled out to `alembic upgrade
head` with DATABASE_URL overridden to TEST_DATABASE_URL -- a subprocess
rather than an in-process call specifically to avoid fighting
get_settings()'s lru_cache and alembic/env.py's own settings read, which
both assume one fixed URL per process. Tables are truncated after each
test that actually touched the DB (not rolled back) since routes commit
explicitly.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.db.session import get_db

BACKEND_DIR = Path(__file__).parent.parent


@pytest.fixture(scope="session")
def test_db_url() -> str:
    settings = get_settings()
    if not settings.test_database_url:
        pytest.fail("TEST_DATABASE_URL must be set (see backend/.env.example) to run this suite")
    return settings.test_database_url


@pytest.fixture(scope="session")
def test_engine(test_db_url: str) -> Generator[Engine, None, None]:
    subprocess.run(
        ["alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env={**os.environ, "DATABASE_URL": test_db_url},
        check=True,
        capture_output=True,
        text=True,
    )
    engine = create_engine(test_db_url, future=True)
    yield engine
    engine.dispose()


def _reset_test_data(engine: Engine) -> None:
    """Deletes every row a test could plausibly have created, without
    touching seed/reference data (system categories: user_id IS NULL).

    Deliberately NOT `TRUNCATE ... CASCADE`: Postgres's CASCADE on TRUNCATE
    empties *any* table with an FK pointing at a truncated one, including
    ones not named in the statement -- it truncated the whole categories
    table (seed rows and all) via its FK to users, which is not what
    "clean up after this test" should mean. Deleting from `users` instead
    relies on every current per-user table's own `ON DELETE CASCADE` (user_settings,
    scenarios, refresh_tokens, password_reset_tokens, and user-owned
    categories via categories.user_id) to clean up everything that hangs
    off a user, while rows with user_id IS NULL are never touched.
    Revisit if a future table holds test data that doesn't cascade from users.
    """
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM users"))


@pytest.fixture()
def db_session(test_engine: Engine) -> Generator[Session, None, None]:
    """A plain session against the test DB, for repository/service tests
    that don't go through the HTTP layer."""
    session_factory = sessionmaker(bind=test_engine, future=True)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        _reset_test_data(test_engine)


@pytest.fixture()
def client(test_engine: Engine) -> Generator[TestClient, None, None]:
    """A TestClient whose get_db dependency is overridden to use the test
    database instead of whatever DATABASE_URL the app process itself was
    started with."""
    from app.main import app

    session_factory = sessionmaker(bind=test_engine, future=True)

    def override_get_db() -> Generator[Session, None, None]:
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    # TestClient reuses one fake client host for every request, so without
    # this, rate-limit counters would leak in from unrelated earlier tests.
    limiter.reset()
    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)
        _reset_test_data(test_engine)
