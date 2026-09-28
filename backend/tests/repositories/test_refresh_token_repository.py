from __future__ import annotations

import threading
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository


def test_try_mark_used_succeeds_once_and_fails_on_reuse(db_session: Session) -> None:
    user = UserRepository(db_session).create(email="claim@example.com", password_hash="hashed")
    token = RefreshTokenRepository(db_session).create(
        user_id=user.id,
        family_id=uuid.uuid4(),
        token_hash="claim-hash",
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    db_session.commit()

    repo = RefreshTokenRepository(db_session)
    assert repo.try_mark_used(token.id) is True
    assert repo.try_mark_used(token.id) is False


def test_concurrent_try_mark_used_on_the_same_token_only_one_side_wins(test_engine: Engine) -> None:
    """The atomicity fix for the client-reported refresh-token rotation
    race: two requests racing to rotate the *same* refresh token must not
    both succeed, or reuse detection is defeated (see auth_service.py's
    refresh() docstring/comments). Uses two real, independent DB sessions
    and a barrier so both UPDATEs are in flight at the same time --
    Postgres's row-level locking on the UPDATE, not application code, is
    what has to serialize them."""
    session_factory = sessionmaker(bind=test_engine, future=True)
    setup = session_factory()
    try:
        user = UserRepository(setup).create(email="race@example.com", password_hash="hashed")
        token = RefreshTokenRepository(setup).create(
            user_id=user.id,
            family_id=uuid.uuid4(),
            token_hash="race-hash",
            expires_at=datetime.now(UTC) + timedelta(days=1),
        )
        token_id = token.id
        setup.commit()
    finally:
        setup.close()

    barrier = threading.Barrier(2)
    results: list[bool] = []
    results_lock = threading.Lock()

    def attempt() -> None:
        session = session_factory()
        try:
            barrier.wait(timeout=5)
            won = RefreshTokenRepository(session).try_mark_used(token_id)
            session.commit()
            with results_lock:
                results.append(won)
        finally:
            session.close()

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert sorted(results) == [False, True]
