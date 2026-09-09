from __future__ import annotations

from sqlalchemy.orm import Session

from app.repositories.user_repository import UserRepository


def test_create_and_get_by_id(db_session: Session) -> None:
    repo = UserRepository(db_session)
    user = repo.create(email="repo@example.com", password_hash="hashed")
    db_session.commit()

    fetched = repo.get_by_id(user.id)
    assert fetched is not None
    assert fetched.email == "repo@example.com"


def test_get_by_email_missing_returns_none(db_session: Session) -> None:
    repo = UserRepository(db_session)
    assert repo.get_by_email("nobody@example.com") is None


def test_get_by_email_is_case_insensitive(db_session: Session) -> None:
    """The `email` column is CITEXT -- this is a DB-level guarantee, but
    worth confirming it actually holds through the ORM mapping."""
    repo = UserRepository(db_session)
    repo.create(email="Mixed.Case@Example.com", password_hash="hashed")
    db_session.commit()

    assert repo.get_by_email("mixed.case@example.com") is not None
