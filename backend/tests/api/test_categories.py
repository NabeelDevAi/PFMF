"""GET /categories: system categories seeded by the data migration."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_categories_requires_auth(client: TestClient) -> None:
    resp = client.get("/v1/categories")
    assert resp.status_code == 401


def test_categories_lists_seeded_system_categories(client: TestClient) -> None:
    register = client.post(
        "/v1/auth/register", json={"email": "cats@example.com", "password": "correct-horse"}
    )
    headers = {"Authorization": f"Bearer {register.json()['access_token']}"}

    resp = client.get("/v1/categories", headers=headers)
    assert resp.status_code == 200
    items = resp.json()["items"]

    keys = {c["key"] for c in items}
    assert "salary" in keys
    assert "rent" in keys
    assert all(c["user_id"] is None for c in items)  # none of these are user-created yet
    assert all(c["name"] is None for c in items)  # system categories carry key, not name

    directions = {c["key"]: c["direction"] for c in items}
    assert directions["salary"] == "income"
    assert directions["rent"] == "expense"
