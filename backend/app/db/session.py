"""Sync SQLAlchemy engine + session factory, and the FastAPI dependency that
hands a request-scoped Session to routers/services.

Sync, not async -- see claude_docs/backend-plan/README.md for why.
"""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: one Session per request, always closed afterward."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
