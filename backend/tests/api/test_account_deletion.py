"""DELETE /me -- permanent account deletion (screen-flow F9), distinct
from DELETE /me/data (reset, tested in test_reset.py)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _register(client: TestClient, email: str = "delacct@example.com") -> dict:
    resp = client.post("/v1/auth/register", json={"email": email, "password": "correct-horse"})
    return resp.json()


def test_delete_account_requires_auth(client: TestClient) -> None:
    resp = client.delete("/v1/me")
    assert resp.status_code == 401


def test_delete_account_removes_the_user(client: TestClient) -> None:
    tokens = _register(client, email="gone@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    resp = client.delete("/v1/me", headers=headers)
    assert resp.status_code == 204

    # The old email can be registered again -- the account is truly gone,
    # not just emptied (that would be reset, not deletion).
    again = client.post(
        "/v1/auth/register", json={"email": "gone@example.com", "password": "another-pass"}
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


def test_deleting_one_account_does_not_affect_another(client: TestClient) -> None:
    victim = _register(client, email="survivor@example.com")
    attacker = _register(client, email="deleter@example.com")

    client.delete("/v1/me", headers={"Authorization": f"Bearer {attacker['access_token']}"})

    resp = client.get("/v1/me", headers={"Authorization": f"Bearer {victim['access_token']}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "survivor@example.com"
