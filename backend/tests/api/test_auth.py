"""Integration tests for the auth API against the real local test database
(backend-plan/11's M2 done-criteria): register/login/refresh/logout,
refresh-token reuse revoking the whole family, and rate limiting."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _register(
    client: TestClient, email: str = "alice@example.com", password: str = "correct-horse"
) -> dict:
    resp = client.post("/v1/auth/register", json={"email": email, "password": password})
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_register_returns_token_pair(client: TestClient) -> None:
    body = _register(client)
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]


def test_register_duplicate_email_is_conflict(client: TestClient) -> None:
    _register(client, email="dup@example.com")
    resp = client.post(
        "/v1/auth/register", json={"email": "dup@example.com", "password": "another-pass"}
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "auth.email_taken"


def test_register_weak_password_is_rejected(client: TestClient) -> None:
    resp = client.post("/v1/auth/register", json={"email": "weak@example.com", "password": "short"})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "auth.weak_password"


def test_register_creates_base_scenario_and_default_settings(client: TestClient) -> None:
    tokens = _register(client, email="withbase@example.com")
    me = client.get("/v1/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert me.status_code == 200
    settings = me.json()["settings"]
    assert settings["currency_code"] == "SAR"
    assert settings["locale"] == "en"
    assert settings["current_balance_minor"] == 0


def test_login_success(client: TestClient) -> None:
    _register(client, email="loginok@example.com", password="correct-horse")
    resp = client.post(
        "/v1/auth/login", json={"email": "loginok@example.com", "password": "correct-horse"}
    )
    assert resp.status_code == 200
    assert resp.json()["access_token"]


def test_login_wrong_password_is_invalid_credentials(client: TestClient) -> None:
    _register(client, email="wrongpw@example.com", password="correct-horse")
    resp = client.post(
        "/v1/auth/login", json={"email": "wrongpw@example.com", "password": "nope-nope"}
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "auth.invalid_credentials"


def test_login_unknown_email_is_invalid_credentials_not_not_found(client: TestClient) -> None:
    """Same code for wrong password and unknown email -- never confirm
    which emails are registered."""
    resp = client.post(
        "/v1/auth/login", json={"email": "nobody@example.com", "password": "whatever1"}
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "auth.invalid_credentials"


def test_refresh_rotates_the_token(client: TestClient) -> None:
    tokens = _register(client, email="rotate@example.com")
    resp = client.post("/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert resp.status_code == 200
    new_tokens = resp.json()
    assert new_tokens["refresh_token"] != tokens["refresh_token"]

    # The new token works.
    resp2 = client.post("/v1/auth/refresh", json={"refresh_token": new_tokens["refresh_token"]})
    assert resp2.status_code == 200


def test_refresh_reuse_of_rotated_token_revokes_whole_family(client: TestClient) -> None:
    tokens = _register(client, email="reuse@example.com")

    first_refresh = client.post("/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert first_refresh.status_code == 200
    newer_tokens = first_refresh.json()

    # Reuse the already-rotated-away-from original token: this is the
    # replay signal. It must fail, AND it must revoke the family --
    # including the legitimately newer token issued just above.
    reused = client.post("/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert reused.status_code == 401
    assert reused.json()["error"]["code"] == "auth.token_invalid"

    also_revoked = client.post(
        "/v1/auth/refresh", json={"refresh_token": newer_tokens["refresh_token"]}
    )
    assert also_revoked.status_code == 401
    assert also_revoked.json()["error"]["code"] == "auth.token_invalid"


def test_refresh_unknown_token_is_invalid(client: TestClient) -> None:
    resp = client.post("/v1/auth/refresh", json={"refresh_token": "not-a-real-token"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "auth.token_invalid"


def test_logout_revokes_the_refresh_token(client: TestClient) -> None:
    tokens = _register(client, email="logout@example.com")
    resp = client.post("/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    assert resp.status_code == 204

    after = client.post("/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert after.status_code == 401


def test_logout_with_unknown_token_is_idempotent(client: TestClient) -> None:
    resp = client.post("/v1/auth/logout", json={"refresh_token": "never-issued"})
    assert resp.status_code == 204


def test_login_rate_limited_after_five_attempts_per_minute(client: TestClient) -> None:
    _register(client, email="ratelimited@example.com", password="correct-horse")
    body = {"email": "ratelimited@example.com", "password": "wrong-one"}

    for _ in range(5):
        resp = client.post("/v1/auth/login", json=body)
        assert resp.status_code == 401

    sixth = client.post("/v1/auth/login", json=body)
    assert sixth.status_code == 429
    assert sixth.json()["error"]["code"] == "rate_limited"


def test_password_reset_flow(client: TestClient, monkeypatch) -> None:
    _register(client, email="reset@example.com", password="original-pw")

    captured: dict[str, str] = {}

    def fake_send(self, *, email: str, token: str) -> None:
        captured["email"] = email
        captured["token"] = token

    from app.services.password_reset_sender import ConsolePasswordResetSender

    monkeypatch.setattr(ConsolePasswordResetSender, "send", fake_send)

    resp = client.post("/v1/auth/password-reset/request", json={"email": "reset@example.com"})
    assert resp.status_code == 204
    assert captured["email"] == "reset@example.com"
    assert captured["token"]

    confirm = client.post(
        "/v1/auth/password-reset/confirm",
        json={"token": captured["token"], "new_password": "brand-new-pw"},
    )
    assert confirm.status_code == 204

    old_login = client.post(
        "/v1/auth/login", json={"email": "reset@example.com", "password": "original-pw"}
    )
    assert old_login.status_code == 401

    new_login = client.post(
        "/v1/auth/login", json={"email": "reset@example.com", "password": "brand-new-pw"}
    )
    assert new_login.status_code == 200


def test_password_reset_request_for_unknown_email_still_returns_204(client: TestClient) -> None:
    """Never reveal whether an email is registered."""
    resp = client.post("/v1/auth/password-reset/request", json={"email": "ghost@example.com"})
    assert resp.status_code == 204


def test_password_reset_confirm_with_bad_token_is_rejected(client: TestClient) -> None:
    resp = client.post(
        "/v1/auth/password-reset/confirm", json={"token": "garbage", "new_password": "whatever12"}
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "auth.reset_token_invalid"
