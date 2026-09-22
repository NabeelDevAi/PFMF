from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.domain.enums import Direction, Recurrence
from app.repositories.scenario_repository import ScenarioRepository
from app.repositories.transaction_repository import TransactionRepository
from app.repositories.user_repository import UserRepository


def test_get_by_id_scoped_to_owner_not_visible_to_another_user(db_session: Session) -> None:
    users = UserRepository(db_session)
    scenarios = ScenarioRepository(db_session)
    transactions = TransactionRepository(db_session)

    owner = users.create(email="owner@example.com", password_hash="x")
    intruder = users.create(email="intruder@example.com", password_hash="x")
    db_session.flush()
    scenario = scenarios.create_base(user_id=owner.id)
    db_session.flush()

    txn = transactions.create(
        user_id=owner.id,
        scenario_id=scenario.id,
        name="Rent",
        amount_minor=300000,
        direction=Direction.EXPENSE,
        recurrence=Recurrence.MONTHLY,
        start_date=date(2026, 1, 1),
    )
    db_session.commit()

    assert transactions.get_by_id(owner.id, txn.id) is not None
    assert transactions.get_by_id(intruder.id, txn.id) is None


def test_list_by_scenario_scoped_to_owner(db_session: Session) -> None:
    users = UserRepository(db_session)
    scenarios = ScenarioRepository(db_session)
    transactions = TransactionRepository(db_session)

    owner = users.create(email="owner2@example.com", password_hash="x")
    intruder = users.create(email="intruder2@example.com", password_hash="x")
    db_session.flush()
    scenario = scenarios.create_base(user_id=owner.id)
    db_session.flush()
    transactions.create(
        user_id=owner.id,
        scenario_id=scenario.id,
        name="Rent",
        amount_minor=300000,
        direction=Direction.EXPENSE,
        recurrence=Recurrence.MONTHLY,
        start_date=date(2026, 1, 1),
    )
    db_session.commit()

    assert len(transactions.list_by_scenario(owner.id, scenario.id)) == 1
    assert transactions.list_by_scenario(intruder.id, scenario.id) == []
