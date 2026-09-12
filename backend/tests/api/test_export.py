"""GET /me/export -- a full, raw backup of everything the user owns
(architecture §9, RFP §4.8)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _auth_headers(client: TestClient, email: str = "export@example.com") -> dict[str, str]:
    resp = client.post("/v1/auth/register", json={"email": email, "password": "correct-horse"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_export_requires_auth(client: TestClient) -> None:
    resp = client.get("/v1/me/export")
    assert resp.status_code == 401


def test_export_of_a_fresh_account_has_base_and_nothing_else(client: TestClient) -> None:
    headers = _auth_headers(client, email="fresh@example.com")
    resp = client.get("/v1/me/export", headers=headers)
    assert resp.status_code == 200
    body = resp.json()

    assert body["user"]["email"] == "fresh@example.com"
    assert body["settings"]["currency_code"] == "SAR"
    assert body["categories"] == []  # no user-created categories yet
    assert len(body["scenarios"]) == 1
    assert body["scenarios"][0]["is_base"] is True
    assert body["transactions"] == []
    assert body["overlays"] == []


def test_export_includes_scenarios_transactions_and_overlays(client: TestClient) -> None:
    headers = _auth_headers(client, email="full@example.com")
    base_id = client.get("/v1/scenarios", headers=headers).json()["items"][0]["id"]

    rent = client.post(
        f"/v1/scenarios/{base_id}/transactions",
        headers=headers,
        json={
            "name": "Rent",
            "amount_minor": 300000,
            "direction": "expense",
            "recurrence": "monthly",
            "start_date": "2026-01-01",
        },
    ).json()
    plan = client.post("/v1/scenarios", headers=headers, json={"name": "Buy House"}).json()
    client.post(
        f"/v1/scenarios/{plan['id']}/overlays",
        headers=headers,
        json={"base_transaction_id": rent["id"], "op": "override", "ovr_amount_minor": 350000},
    )

    resp = client.get("/v1/me/export", headers=headers)
    body = resp.json()

    scenario_ids = {s["id"] for s in body["scenarios"]}
    assert scenario_ids == {base_id, plan["id"]}

    assert len(body["transactions"]) == 1
    assert body["transactions"][0]["id"] == rent["id"]
    assert body["transactions"][0]["scenario_id"] == base_id
    assert "origin" not in body["transactions"][0]  # raw row, not a resolved view

    assert len(body["overlays"]) == 1
    assert body["overlays"][0]["base_transaction_id"] == rent["id"]
    assert body["overlays"][0]["ovr_amount_minor"] == 350000


def test_export_includes_archived_scenarios(client: TestClient) -> None:
    headers = _auth_headers(client, email="archived@example.com")
    plan = client.post("/v1/scenarios", headers=headers, json={"name": "Someday"}).json()
    client.post(f"/v1/scenarios/{plan['id']}/archive", headers=headers)

    # Archived scenarios are hidden from the default list...
    assert plan["id"] not in {
        s["id"] for s in client.get("/v1/scenarios", headers=headers).json()["items"]
    }
    # ...but a full data export must still include them.
    body = client.get("/v1/me/export", headers=headers).json()
    assert plan["id"] in {s["id"] for s in body["scenarios"]}


def test_export_includes_user_created_categories_but_not_system_ones(client: TestClient) -> None:
    """No endpoint creates a user category yet (a known small gap, see
    backend-plan/12) -- this documents the intended shape for when one
    exists, and confirms system categories are excluded either way."""
    headers = _auth_headers(client, email="cats@example.com")
    body = client.get("/v1/me/export", headers=headers).json()
    assert body["categories"] == []

    all_categories = client.get("/v1/categories", headers=headers).json()["items"]
    assert len(all_categories) > 0  # system categories exist and are visible...
    assert all(c["user_id"] is None for c in all_categories)  # ...but none are user-owned yet


def test_export_does_not_leak_another_users_data(client: TestClient) -> None:
    headers_a = _auth_headers(client, email="owner6@example.com")
    headers_b = _auth_headers(client, email="other6@example.com")
    base_a = client.get("/v1/scenarios", headers=headers_a).json()["items"][0]["id"]
    client.post(
        f"/v1/scenarios/{base_a}/transactions",
        headers=headers_a,
        json={
            "name": "Secret",
            "amount_minor": 1000,
            "direction": "expense",
            "recurrence": "monthly",
            "start_date": "2026-01-01",
        },
    )

    body_b = client.get("/v1/me/export", headers=headers_b).json()
    assert body_b["transactions"] == []
    assert all(s["is_base"] for s in body_b["scenarios"])  # only B's own Base
