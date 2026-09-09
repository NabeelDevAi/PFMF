"""GET /me and PATCH /me/settings, plus the auth dependency itself."""

from __future__ import annotations

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
        json={
            "display_name": "Nabeel",
            "currency_code": "USD",
            "locale": "ar",
            "opening_balance_minor": 450000,
            "opening_balance_date": "2026-01-01",
        },
    )
    assert resp.status_code == 200
    settings = resp.json()["settings"]
    assert settings["display_name"] == "Nabeel"
    assert settings["currency_code"] == "USD"
    assert settings["locale"] == "ar"
    assert settings["opening_balance_minor"] == 450000
    assert settings["opening_balance_date"] == "2026-01-01"


def test_patch_settings_partial_update_leaves_other_fields_untouched(client: TestClient) -> None:
    headers = _register_and_auth_headers(client, email="partial@example.com")
    client.patch("/v1/me/settings", headers=headers, json={"currency_code": "USD"})
    resp = client.patch("/v1/me/settings", headers=headers, json={"display_name": "Only This"})
    assert resp.status_code == 200
    settings = resp.json()["settings"]
    assert settings["display_name"] == "Only This"
    assert settings["currency_code"] == "USD"  # untouched by the second patch
