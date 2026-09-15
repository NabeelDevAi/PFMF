"""GET /me, PATCH /me/settings, PUT /me/balance, plus the auth dependency
itself. The balance endpoint is deliberately separate from settings
(architecture §9.1, D-04) -- see the tests below asserting settings can't
touch it."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient


def _register_and_auth_headers(client: TestClient, email: str = "me@example.com") -> dict[str, str]:
    resp = client.post("/v1/auth/register", json={"email": email, "password": "correct-horse"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_get_me_without_token_is_rejected(client: TestClient) -> None:
    resp = client.get("/v1/me")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "auth.token_invalid"


def test_get_me_with_garbage_token_is_rejected(client: TestClient) -> None:
    resp = client.get("/v1/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "auth.token_invalid"


def test_get_me_returns_profile_and_settings(client: TestClient) -> None:
    headers = _register_and_auth_headers(client)
    resp = client.get("/v1/me", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "me@example.com"
    assert "settings" in body


def test_patch_settings_updates_and_returns_new_values(client: TestClient) -> None:
    headers = _register_and_auth_headers(client, email="patch@example.com")
    resp = client.patch(
        "/v1/me/settings",
        headers=headers,
        json={"display_name": "Nabeel", "currency_code": "USD", "locale": "ar"},
    )
    assert resp.status_code == 200
    settings = resp.json()["settings"]
    assert settings["display_name"] == "Nabeel"
    assert settings["currency_code"] == "USD"
    assert settings["locale"] == "ar"


def test_patch_settings_partial_update_leaves_other_fields_untouched(client: TestClient) -> None:
    headers = _register_and_auth_headers(client, email="partial@example.com")
    client.patch("/v1/me/settings", headers=headers, json={"currency_code": "USD"})
    resp = client.patch("/v1/me/settings", headers=headers, json={"display_name": "Only This"})
    assert resp.status_code == 200
    settings = resp.json()["settings"]
    assert settings["display_name"] == "Only This"
    assert settings["currency_code"] == "USD"  # untouched by the second patch


def test_patch_settings_cannot_touch_the_balance_fields(client: TestClient) -> None:
    """D-04: the Current Cash Balance is only ever written by PUT
    /me/balance. SettingsPatch doesn't declare these fields at all, so
    Pydantic silently drops them rather than erroring -- this pins that
    behavior instead of just asserting the schema by inspection."""
    headers = _register_and_auth_headers(client, email="noleak@example.com")
    before = client.get("/v1/me", headers=headers).json()["settings"]

    resp = client.patch(
        "/v1/me/settings",
        headers=headers,
        json={"current_balance_minor": 999999999, "balance_as_of": "2020-01-01"},
    )
    assert resp.status_code == 200
    after = resp.json()["settings"]
    assert after["current_balance_minor"] == before["current_balance_minor"]
    assert after["balance_as_of"] == before["balance_as_of"]


def test_put_balance_updates_amount_and_as_of(client: TestClient) -> None:
    headers = _register_and_auth_headers(client, email="balance@example.com")

    resp = client.put(
        "/v1/me/balance",
        headers=headers,
        json={"current_balance_minor": 4500000, "balance_as_of": "2026-01-15"},
    )
    assert resp.status_code == 200
    settings = resp.json()["settings"]
    assert settings["current_balance_minor"] == 4500000
    assert settings["balance_as_of"] == "2026-01-15"

    # Persisted, not just echoed back.
    settings = client.get("/v1/me", headers=headers).json()["settings"]
    assert settings["current_balance_minor"] == 4500000
    assert settings["balance_as_of"] == "2026-01-15"


def test_put_balance_rejects_an_as_of_date_in_the_future(client: TestClient) -> None:
    headers = _register_and_auth_headers(client, email="futuredate@example.com")
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    resp = client.put(
        "/v1/me/balance",
        headers=headers,
        json={"current_balance_minor": 100000, "balance_as_of": tomorrow},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "balance.as_of_in_future"


def test_put_balance_rejects_an_as_of_date_beyond_the_backstop(client: TestClient) -> None:
    headers = _register_and_auth_headers(client, email="ancient@example.com")
    too_old = (date.today() - timedelta(days=365 * 6)).isoformat()

    resp = client.put(
        "/v1/me/balance",
        headers=headers,
        json={"current_balance_minor": 100000, "balance_as_of": too_old},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "balance.as_of_too_old"


def test_put_balance_accepts_todays_date(client: TestClient) -> None:
    headers = _register_and_auth_headers(client, email="todaydate@example.com")

    resp = client.put(
        "/v1/me/balance",
        headers=headers,
        json={"current_balance_minor": 100000, "balance_as_of": date.today().isoformat()},
    )
    assert resp.status_code == 200


def test_put_balance_requires_auth(client: TestClient) -> None:
    resp = client.put(
        "/v1/me/balance", json={"current_balance_minor": 100000, "balance_as_of": "2026-01-01"}
    )
    assert resp.status_code == 401
