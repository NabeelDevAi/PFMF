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


def test_soft_delete_hides_the_user_from_ordinary_lookups(db_session: Session) -> None:
    """DELETE /me's actual mechanism (product decision, AccountService):
    the row stays, but get_by_id/get_by_email must treat it as gone --
    that's what makes an already-issued token stop working immediately
    and a login attempt fail, without anything cascading."""
    repo = UserRepository(db_session)
    user = repo.create(email="softdel@example.com", password_hash="hashed")
    db_session.commit()
    user_id = user.id

    repo.soft_delete(user)
    db_session.commit()

    assert repo.get_by_id(user_id) is None
    assert repo.get_by_email("softdel@example.com") is None


def test_soft_deleted_email_can_be_reused_by_a_new_row(db_session: Session) -> None:
    """The partial unique index (migration 0017) only enforces uniqueness
    among active rows -- a soft-deleted row must never block a brand-new
    registration with the same email."""
    repo = UserRepository(db_session)
    original = repo.create(email="reused@example.com", password_hash="hashed")
    db_session.commit()
    repo.soft_delete(original)
    db_session.commit()

    new_user = repo.create(email="reused@example.com", password_hash="different-hash")
    db_session.commit()

    assert new_user.id != original.id
    fetched = repo.get_by_email("reused@example.com")
    assert fetched is not None
    assert fetched.id == new_user.id  # resolves to the new row, not the old one
