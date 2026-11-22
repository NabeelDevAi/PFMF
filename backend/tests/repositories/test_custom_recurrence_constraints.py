"""The database itself enforces the custom-recurrence rules (UAT-004), so a
bug in a service can never store an invalid row."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models.scenario_overlay import ScenarioOverlay
from app.domain.enums import Direction, OverlayOp, Recurrence, RecurrenceUnit
from app.repositories.scenario_repository import ScenarioRepository
from app.repositories.transaction_repository import TransactionRepository
from app.repositories.user_repository import UserRepository


def _setup(db_session: Session):
    user = UserRepository(db_session).create(email="constraints@example.com", password_hash="x")
    db_session.flush()
    scenarios = ScenarioRepository(db_session)
    base = scenarios.create_base(user_id=user.id)
    derived = scenarios.create(user_id=user.id, name="Derived")
    db_session.flush()
    return user, base, derived, TransactionRepository(db_session)


def _create(transactions: TransactionRepository, user, base, **fields):
    return transactions.create(
        user_id=user.id,
        scenario_id=base.id,
        name="Rule",
        amount_minor=100,
        direction=Direction.EXPENSE,
        start_date=date(2026, 1, 1),
        **fields,
    )


def test_a_valid_custom_row_is_stored(db_session: Session) -> None:
    user, base, _derived, transactions = _setup(db_session)
    txn = _create(
        transactions,
        user,
        base,
        recurrence=Recurrence.CUSTOM,
        recurrence_interval=4,
        recurrence_unit=RecurrenceUnit.MONTH,
    )
    db_session.commit()
    assert (txn.recurrence_interval, txn.recurrence_unit) == (4, RecurrenceUnit.MONTH)


@pytest.mark.parametrize(
    "fields",
    [
        {"recurrence": Recurrence.CUSTOM},
        {"recurrence": Recurrence.CUSTOM, "recurrence_interval": 4},
        {"recurrence": Recurrence.CUSTOM, "recurrence_unit": RecurrenceUnit.DAY},
        {"recurrence": Recurrence.MONTHLY, "recurrence_interval": 1},
        {"recurrence": Recurrence.MONTHLY, "recurrence_unit": RecurrenceUnit.MONTH},
        {
            "recurrence": Recurrence.CUSTOM,
            "recurrence_interval": 0,
            "recurrence_unit": RecurrenceUnit.DAY,
        },
        {
            "recurrence": Recurrence.CUSTOM,
            "recurrence_interval": 1000,
            "recurrence_unit": RecurrenceUnit.DAY,
        },
        {
            "recurrence": Recurrence.CUSTOM,
            "recurrence_interval": -1,
            "recurrence_unit": RecurrenceUnit.DAY,
        },
    ],
)
def test_invalid_transaction_rows_are_rejected_by_the_database(
    db_session: Session, fields: dict
) -> None:
    user, base, _derived, transactions = _setup(db_session)
    with pytest.raises(IntegrityError):
        _create(transactions, user, base, **fields)
        db_session.flush()
    db_session.rollback()


@pytest.mark.parametrize(
    "fields",
    [
        {"ovr_recurrence": Recurrence.CUSTOM},
        {"ovr_recurrence": Recurrence.CUSTOM, "ovr_recurrence_interval": 3},
        {"ovr_recurrence": Recurrence.MONTHLY, "ovr_recurrence_interval": 3},
        {"ovr_recurrence_interval": 3, "ovr_recurrence_unit": RecurrenceUnit.DAY},
        {
            "ovr_recurrence": Recurrence.CUSTOM,
            "ovr_recurrence_interval": 0,
            "ovr_recurrence_unit": RecurrenceUnit.WEEK,
        },
    ],
)
def test_invalid_overlay_rows_are_rejected_by_the_database(
    db_session: Session, fields: dict
) -> None:
    user, base, derived, transactions = _setup(db_session)
    target = _create(transactions, user, base, recurrence=Recurrence.MONTHLY)
    db_session.flush()
    with pytest.raises(IntegrityError):
        db_session.add(
            ScenarioOverlay(
                scenario_id=derived.id,
                base_transaction_id=target.id,
                op=OverlayOp.OVERRIDE,
                **fields,
            )
        )
        db_session.flush()
    db_session.rollback()


def test_a_valid_custom_overlay_row_is_stored(db_session: Session) -> None:
    user, base, derived, transactions = _setup(db_session)
    target = _create(transactions, user, base, recurrence=Recurrence.MONTHLY)
    db_session.flush()
    db_session.add(
        ScenarioOverlay(
            scenario_id=derived.id,
            base_transaction_id=target.id,
            op=OverlayOp.OVERRIDE,
            ovr_recurrence=Recurrence.CUSTOM,
            ovr_recurrence_interval=2,
            ovr_recurrence_unit=RecurrenceUnit.YEAR,
        )
    )
    db_session.commit()
