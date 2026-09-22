"""DELETE /me -- account deletion (screen-flow F9), distinct from
DELETE /me/data (reset, tested in test_reset.py). Product decision:
this is a soft delete -- it behaves like a hard delete from the user's
side (every test below holds), but the row and its data physically
survive for Phase 2's scheduled purge (see
12-open-questions-and-future-hardening.md and
tests/repositories/test_user_repository.py for the mechanism itself)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.scenario import Scenario
from app.db.models.user import User


def _register(client: TestClient, email: str = "delacct@example.com") -> dict:
    resp = client.post(
        "/v1/auth/register", json={"email": email, "password": "correct-horse", "name": "Test User"}
    )
    return resp.json()


def test_delete_account_requires_auth(client: TestClient) -> None:
    resp = client.delete("/v1/me")
    assert resp.status_code == 401


def test_delete_account_removes_the_user(client: TestClient) -> None:
    tokens = _register(client, email="gone@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    resp = client.delete("/v1/me", headers=headers)
    assert resp.status_code == 200

    # The old email can be registered again -- the account is truly gone,
    # not just emptied (that would be reset, not deletion).
    again = client.post(
        "/v1/auth/register",
        json={"email": "gone@example.com", "password": "another-pass", "name": "Test User"},
    )
    assert again.status_code == 201


def test_access_token_stops_working_immediately_after_deletion(client: TestClient) -> None:
    tokens = _register(client, email="deadtoken@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    client.delete("/v1/me", headers=headers)

    resp = client.get("/v1/me", headers=headers)
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "auth.token_invalid"


def test_refresh_token_stops_working_after_deletion(client: TestClient) -> None:
    tokens = _register(client, email="deadrefresh@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    client.delete("/v1/me", headers=headers)

    resp = client.post("/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert resp.status_code == 401


def test_deleted_account_data_physically_survives_for_phase_2(
    client: TestClient, db_session: Session
) -> None:
    """The user row and everything it owns (here: its Base Plan) must
    still be in the database after DELETE /me -- only access is gone.
    Phase 2's scheduled job is what actually purges this later."""
    tokens = _register(client, email="softdelete@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    user_id = client.get("/v1/me", headers=headers).json()["id"]

    resp = client.delete("/v1/me", headers=headers)
    assert resp.status_code == 200

    user = db_session.scalar(select(User).where(User.id == user_id))
    assert user is not None
    assert user.deleted_at is not None

    base_plan = db_session.scalar(select(Scenario).where(Scenario.user_id == user_id))
    assert base_plan is not None  # not cascaded away -- nothing was actually deleted


def test_deleting_one_account_does_not_affect_another(client: TestClient) -> None:
    victim = _register(client, email="survivor@example.com")
    attacker = _register(client, email="deleter@example.com")

    client.delete("/v1/me", headers={"Authorization": f"Bearer {attacker['access_token']}"})

    resp = client.get("/v1/me", headers={"Authorization": f"Bearer {victim['access_token']}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "survivor@example.com"
