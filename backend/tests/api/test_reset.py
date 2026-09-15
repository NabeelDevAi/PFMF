"""DELETE /me/data -- account reset (architecture §9, RFP §4.8).
Deletes every derived scenario and Base's own transactions, resets the
Current Cash Balance, but never deletes Base itself or the account, and never
touches currency/locale/display_name. See reset_service.py's docstring
for why the boundary was drawn there."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _auth_headers(client: TestClient, email: str = "reset@example.com") -> dict[str, str]:
    resp = client.post("/v1/auth/register", json={"email": email, "password": "correct-horse"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _setup_data(client: TestClient, headers: dict) -> dict:
    client.put(
        "/v1/me/balance",
        headers=headers,
        json={"current_balance_minor": 500000, "balance_as_of": "2026-01-01"},
    )
    client.patch(
        "/v1/me/settings",
        headers=headers,
        json={"currency_code": "USD", "locale": "ar", "display_name": "Nabeel"},
    )
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
        json={"base_transaction_id": rent["id"], "op": "exclude"},
    )
    return {"base_id": base_id, "rent": rent, "plan": plan}


def test_reset_requires_auth(client: TestClient) -> None:
    resp = client.delete("/v1/me/data")
    assert resp.status_code == 401


def test_reset_deletes_derived_scenarios_and_base_transactions(client: TestClient) -> None:
    headers = _auth_headers(client, email="wipe@example.com")
    setup = _setup_data(client, headers)

    resp = client.delete("/v1/me/data", headers=headers)
    assert resp.status_code == 204

    scenarios = client.get("/v1/scenarios?include_archived=true", headers=headers).json()["items"]
    assert len(scenarios) == 1
    assert scenarios[0]["id"] == setup["base_id"]
    assert scenarios[0]["is_base"] is True

    base_txns = client.get(f"/v1/scenarios/{setup['base_id']}/transactions", headers=headers).json()
    assert base_txns["items"] == []


def test_reset_deletes_overlays_via_scenario_cascade(client: TestClient) -> None:
    headers = _auth_headers(client, email="wipeoverlay@example.com")
    setup = _setup_data(client, headers)

    client.delete("/v1/me/data", headers=headers)

    export = client.get("/v1/me/export", headers=headers).json()
    assert export["overlays"] == []
    assert setup["plan"]["id"] not in {s["id"] for s in export["scenarios"]}


def test_reset_resets_current_balance_but_keeps_preferences(client: TestClient) -> None:
    headers = _auth_headers(client, email="wipebalance@example.com")
    _setup_data(client, headers)

    client.delete("/v1/me/data", headers=headers)

    me = client.get("/v1/me", headers=headers).json()
    assert me["settings"]["current_balance_minor"] == 0
    # Preferences survive a reset -- they aren't "data" in the RFP §4.8 sense.
    assert me["settings"]["currency_code"] == "USD"
    assert me["settings"]["locale"] == "ar"
    assert me["settings"]["display_name"] == "Nabeel"


def test_reset_forecast_still_works_afterward(client: TestClient) -> None:
    """Base must survive in a genuinely usable state -- a flat ledger at
    the reset Current Cash Balance, not a broken account."""
    headers = _auth_headers(client, email="wipeforecast@example.com")
    setup = _setup_data(client, headers)

    client.delete("/v1/me/data", headers=headers)

    resp = client.get(
        f"/v1/scenarios/{setup['base_id']}/forecast", headers=headers, params={"horizon": 12}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["current_balance_minor"] == 0
    assert all(m["closing_balance_minor"] == 0 for m in body["months"])


def test_reset_deletes_user_created_categories(client: TestClient) -> None:
    headers = _auth_headers(client, email="wipecats@example.com")
    client.delete("/v1/me/data", headers=headers)  # no-op today (no user categories exist yet)

    export = client.get("/v1/me/export", headers=headers).json()
    assert export["categories"] == []
    system_categories = client.get("/v1/categories", headers=headers).json()["items"]
    assert len(system_categories) > 0  # system categories are untouched by any user's reset


def test_reset_does_not_affect_another_user(client: TestClient) -> None:
    headers_a = _auth_headers(client, email="victim@example.com")
    headers_b = _auth_headers(client, email="resetter@example.com")
    base_a = client.get("/v1/scenarios", headers=headers_a).json()["items"][0]["id"]
    client.post(
        f"/v1/scenarios/{base_a}/transactions",
        headers=headers_a,
        json={
            "name": "Safe",
            "amount_minor": 1000,
            "direction": "expense",
            "recurrence": "monthly",
            "start_date": "2026-01-01",
        },
    )

    client.delete("/v1/me/data", headers=headers_b)

    a_txns = client.get(f"/v1/scenarios/{base_a}/transactions", headers=headers_a).json()["items"]
    assert len(a_txns) == 1
