"""ScenarioResolver: the bridge between persistence and the pure engine.
backend-plan/06 calls this out for the heaviest test coverage in the
backend -- every case here maps directly to architecture §6's resolution
algorithm, plus the isolation guarantee (§9.2) proven against the real
database, and the one named edge case deferred all the way from M1
(unset_end_date on a previously-ending transaction, architecture §12.2).
"""

from __future__ import annotations

import uuid
from datetime import date

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy.orm import Session

from app.db.models.scenario_overlay import ScenarioOverlay
from app.domain.enums import Direction, OverlayOp, Recurrence
from app.engine.types import Direction as EngineDirection
from app.engine.types import Origin as EngineOrigin
from app.repositories.scenario_repository import ScenarioRepository
from app.repositories.transaction_repository import TransactionRepository
from app.repositories.user_repository import UserRepository
from app.services.scenario_resolver import ScenarioResolver


def _setup(db_session: Session):
    users = UserRepository(db_session)
    scenarios = ScenarioRepository(db_session)
    transactions = TransactionRepository(db_session)

    user = users.create(email="resolver@example.com", password_hash="x")
    db_session.flush()
    base = scenarios.create_base(user_id=user.id)
    derived = scenarios.create(user_id=user.id, name="Buy House")
    db_session.flush()

    rent = transactions.create(
        user_id=user.id,
        scenario_id=base.id,
        name="Rent",
        amount_minor=300000,
        direction=Direction.EXPENSE,
        recurrence=Recurrence.MONTHLY,
        start_date=date(2026, 1, 1),
    )
    salary = transactions.create(
        user_id=user.id,
        scenario_id=base.id,
        name="Salary",
        amount_minor=900000,
        direction=Direction.INCOME,
        recurrence=Recurrence.MONTHLY,
        start_date=date(2026, 1, 25),
    )
    db_session.commit()
    return user, base, derived, rent, salary


def test_base_resolves_to_its_own_transactions_with_origin_own(db_session: Session) -> None:
    user, base, _derived, rent, salary = _setup(db_session)
    resolved = ScenarioResolver(db_session).resolve(user.id, base)

    assert {r.source_id for r in resolved} == {str(rent.id), str(salary.id)}
    assert all(r.origin is EngineOrigin.OWN for r in resolved)


def test_derived_scenario_with_no_overlays_inherits_everything(db_session: Session) -> None:
    user, base, derived, rent, salary = _setup(db_session)
    resolved = ScenarioResolver(db_session).resolve(user.id, derived)

    assert {r.source_id for r in resolved} == {str(rent.id), str(salary.id)}
    assert all(r.origin is EngineOrigin.INHERITED for r in resolved)
    rent_resolved = next(r for r in resolved if r.source_id == str(rent.id))
    assert rent_resolved.amount_minor == 300000
    assert rent_resolved.name == "Rent"


def test_exclude_overlay_removes_the_transaction_from_resolution(db_session: Session) -> None:
    user, base, derived, rent, salary = _setup(db_session)
    overlay = ScenarioOverlay(
        scenario_id=derived.id, base_transaction_id=rent.id, op=OverlayOp.EXCLUDE
    )
    db_session.add(overlay)
    db_session.commit()

    resolved = ScenarioResolver(db_session).resolve(user.id, derived)
    assert {r.source_id for r in resolved} == {str(salary.id)}


def test_override_overlay_patches_only_the_given_fields(db_session: Session) -> None:
    user, base, derived, rent, salary = _setup(db_session)
    overlay = ScenarioOverlay(
        scenario_id=derived.id,
        base_transaction_id=rent.id,
        op=OverlayOp.OVERRIDE,
        ovr_amount_minor=350000,
    )
    db_session.add(overlay)
    db_session.commit()

    resolved = ScenarioResolver(db_session).resolve(user.id, derived)
    rent_resolved = next(r for r in resolved if r.source_id == str(rent.id))

    assert rent_resolved.origin is EngineOrigin.OVERRIDDEN
    assert rent_resolved.amount_minor == 350000  # overridden
    assert rent_resolved.name == "Rent"  # untouched, still Base's value
    assert rent_resolved.direction is EngineDirection.EXPENSE  # never overridable


def test_unset_end_date_overlay_makes_a_previously_ending_transaction_open_ended(
    db_session: Session,
) -> None:
    """Named edge case from architecture §12.2, deferred from M1 (engine
    has no concept of overlays) to here, where it actually applies."""
    user, base, derived, rent, _salary = _setup(db_session)
    transactions = TransactionRepository(db_session)
    txn = transactions.get_by_id(user.id, rent.id)
    txn.end_date = date(2026, 12, 1)
    db_session.commit()

    overlay = ScenarioOverlay(
        scenario_id=derived.id,
        base_transaction_id=rent.id,
        op=OverlayOp.OVERRIDE,
        unset_end_date=True,
    )
    db_session.add(overlay)
    db_session.commit()

    resolved = ScenarioResolver(db_session).resolve(user.id, derived)
    rent_resolved = next(r for r in resolved if r.source_id == str(rent.id))
    assert rent_resolved.end_date is None

    # Base itself is untouched -- still has its end_date.
    base_resolved = ScenarioResolver(db_session).resolve(user.id, base)
    base_rent = next(r for r in base_resolved if r.source_id == str(rent.id))
    assert base_rent.end_date == date(2026, 12, 1)


def test_scenarios_own_additions_have_origin_added(db_session: Session) -> None:
    user, base, derived, rent, salary = _setup(db_session)
    transactions = TransactionRepository(db_session)
    mortgage = transactions.create(
        user_id=user.id,
        scenario_id=derived.id,
        name="Mortgage",
        amount_minor=250000,
        direction=Direction.EXPENSE,
        recurrence=Recurrence.MONTHLY,
        start_date=date(2026, 1, 1),
    )
    db_session.commit()

    resolved = ScenarioResolver(db_session).resolve(user.id, derived)
    mortgage_resolved = next(r for r in resolved if r.source_id == str(mortgage.id))
    assert mortgage_resolved.origin is EngineOrigin.ADDED


def test_override_never_mutates_the_underlying_base_transaction_row(db_session: Session) -> None:
    """The isolation guarantee, proven at the row level: resolving an
    override must never flush a change onto Base's actual transaction."""
    user, base, derived, rent, _salary = _setup(db_session)
    overlay = ScenarioOverlay(
        scenario_id=derived.id,
        base_transaction_id=rent.id,
        op=OverlayOp.OVERRIDE,
        ovr_amount_minor=999999,
        ovr_name="Renamed",
    )
    db_session.add(overlay)
    db_session.commit()

    ScenarioResolver(db_session).resolve(user.id, derived)
    db_session.commit()  # if resolution dirtied the row, this would persist it

    transactions = TransactionRepository(db_session)
    fresh = transactions.get_by_id(user.id, rent.id)
    assert fresh.amount_minor == 300000
    assert fresh.name == "Rent"


def test_isolation_arbitrary_overlays_on_one_scenario_never_affect_another(
    db_session: Session,
) -> None:
    """Architecture §9.2 / backend-plan §10's isolation invariant, proven
    against the real database: scenario A's resolved view (and Base's own)
    must be identical before and after B is overlaid every possible way.
    M1 check 29.3."""
    user, base, _derived, rent, salary = _setup(db_session)
    scenarios = ScenarioRepository(db_session)
    scenario_a = scenarios.create(user_id=user.id, name="Scenario A")
    scenario_b = scenarios.create(user_id=user.id, name="Scenario B")
    db_session.commit()

    resolver = ScenarioResolver(db_session)
    a_before = resolver.resolve(user.id, scenario_a)
    base_before = resolver.resolve(user.id, base)

    db_session.add_all(
        [
            ScenarioOverlay(
                scenario_id=scenario_b.id, base_transaction_id=rent.id, op=OverlayOp.EXCLUDE
            ),
            ScenarioOverlay(
                scenario_id=scenario_b.id,
                base_transaction_id=salary.id,
                op=OverlayOp.OVERRIDE,
                ovr_amount_minor=1000000,
            ),
        ]
    )
    db_session.commit()

    a_after = resolver.resolve(user.id, scenario_a)
    base_after = resolver.resolve(user.id, base)

    assert a_before == a_after
    assert base_before == base_after


@st.composite
def _domain_transaction_spec(draw: st.DrawFn) -> dict:
    recurrence = draw(st.sampled_from(list(Recurrence)))
    start_date = draw(st.dates(min_value=date(2018, 1, 1), max_value=date(2032, 12, 31)))
    end_date = (
        None
        if recurrence is Recurrence.ONE_TIME
        else draw(st.none() | st.dates(min_value=start_date, max_value=date(2033, 12, 31)))
    )
    return {
        "name": "txn",
        "amount_minor": draw(st.integers(min_value=1, max_value=5_000_000)),
        "direction": draw(st.sampled_from(list(Direction))),
        "recurrence": recurrence,
        "start_date": start_date,
        "end_date": end_date,
        "category_id": None,
        "notes": None,
    }


@st.composite
def _overlay_spec(draw: st.DrawFn) -> dict:
    op = draw(st.sampled_from(list(OverlayOp)))
    ovr_amount_minor = (
        None if op is OverlayOp.EXCLUDE else draw(st.integers(min_value=1, max_value=5_000_000))
    )
    return {"op": op, "ovr_amount_minor": ovr_amount_minor}


@given(
    base_specs=st.lists(_domain_transaction_spec(), min_size=1, max_size=8),
    data=st.data(),
)
@settings(
    max_examples=25,
    deadline=None,
    # db_session is deliberately shared across every example in this one
    # test, not recreated per example: each example creates its own fresh
    # user (unique uuid email) and never touches another example's rows,
    # so there's nothing to reset between them, and cleanup happens once,
    # after the whole test, via db_session's own teardown.
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_isolation_property(
    db_session: Session, base_specs: list[dict], data: st.DataObject
) -> None:
    """Architecture §12.3's isolation invariant, generated: arbitrary
    overlays applied to scenario B must never change scenario A's
    resolved view, or Base's own -- against the real database, with
    randomized Base transactions and randomized overlays targeting a
    randomized subset of them. M1 check 29.3."""
    users = UserRepository(db_session)
    scenarios = ScenarioRepository(db_session)
    transactions = TransactionRepository(db_session)

    user = users.create(email=f"iso-{uuid.uuid4()}@example.com", password_hash="x")
    db_session.flush()
    base = scenarios.create_base(user_id=user.id)
    scenario_a = scenarios.create(user_id=user.id, name="A")
    scenario_b = scenarios.create(user_id=user.id, name="B")
    db_session.flush()

    base_txns = [
        transactions.create(user_id=user.id, scenario_id=base.id, **spec) for spec in base_specs
    ]
    db_session.commit()

    resolver = ScenarioResolver(db_session)
    a_before = resolver.resolve(user.id, scenario_a)
    base_before = resolver.resolve(user.id, base)

    targets = data.draw(
        st.lists(st.sampled_from(base_txns), unique_by=lambda t: t.id, max_size=len(base_txns))
    )
    for txn in targets:
        overlay_spec = data.draw(_overlay_spec())
        db_session.add(
            ScenarioOverlay(scenario_id=scenario_b.id, base_transaction_id=txn.id, **overlay_spec)
        )
    db_session.commit()

    a_after = resolver.resolve(user.id, scenario_a)
    base_after = resolver.resolve(user.id, base)

    assert a_before == a_after
    assert base_before == base_after
