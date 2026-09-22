"""Cross-user isolation is a first-class test category at the repository
layer (backend-plan/05-repositories-module.md §4), not an afterthought
bundled into a CRUD test."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.repositories.scenario_repository import ScenarioRepository
from app.repositories.user_repository import UserRepository


def test_get_base_only_returns_this_users_base_scenario(db_session: Session) -> None:
    users = UserRepository(db_session)
    scenarios = ScenarioRepository(db_session)

    user_a = users.create(email="a@example.com", password_hash="x")
    user_b = users.create(email="b@example.com", password_hash="x")
    db_session.flush()

    base_a = scenarios.create_base(user_id=user_a.id, name="A's Base")
    base_b = scenarios.create_base(user_id=user_b.id, name="B's Base")
    db_session.commit()

    assert scenarios.get_base(user_a.id).id == base_a.id
    assert scenarios.get_base(user_b.id).id == base_b.id
    assert scenarios.get_base(user_a.id).id != base_b.id


def test_get_base_returns_none_when_user_has_no_scenarios(db_session: Session) -> None:
    users = UserRepository(db_session)
    scenarios = ScenarioRepository(db_session)

    user = users.create(email="nobase@example.com", password_hash="x")
    db_session.commit()

    assert scenarios.get_base(user.id) is None
