"""GET /me, PATCH /me/settings, PUT /me/balance, PATCH /me/password, plus
the auth dependency itself. The balance endpoint is deliberately separate
from settings (architecture §9.1, D-04) -- see the tests below asserting
settings can't touch it. No forgot/reset-password-via-email flow in
Phase 1 -- PATCH /me/password (tested below) is the only way to change
a password, and it requires an active session."""

from __future__ import annotations

import base64
from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.core.avatar_storage import avatars_dir
from app.core.config import get_settings

# Only the leading signature bytes matter to save_avatar()'s magic-byte
# sniff (app/core/avatar_storage.py) -- it deliberately doesn't parse a
# real image structure, so a fixture matching just the signature is
# exactly what the code actually checks, not more.
_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"fake-but-signature-matches-png"
_PNG_BASE64 = base64.b64encode(_PNG_BYTES).decode()


def _register_and_auth_headers(client: TestClient, email: str = "me@example.com") -> dict[str, str]:
    resp = client.post(
        "/v1/auth/register", json={"email": email, "password": "correct-horse", "name": "Test User"}
    )
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


def test_get_me_has_no_avatar_by_default(client: TestClient) -> None:
    headers = _register_and_auth_headers(client, email="noavatar@example.com")
    settings = client.get("/v1/me", headers=headers).json()["settings"]
    assert settings["avatar_url"] is None


def test_patch_settings_uploads_an_avatar(client: TestClient) -> None:
    headers = _register_and_auth_headers(client, email="avatar1@example.com")

    resp = client.patch("/v1/me/settings", headers=headers, json={"avatar_base64": _PNG_BASE64})
    assert resp.status_code == 200
    avatar_url = resp.json()["settings"]["avatar_url"]
    assert avatar_url is not None
    assert avatar_url.startswith("/static/avatars/")
    assert avatar_url.endswith(".png")

    filename = avatar_url.removeprefix("/static/avatars/")
    path = avatars_dir() / filename
    assert path.read_bytes() == _PNG_BYTES
    path.unlink()  # test hygiene -- don't leave files behind


def test_patch_settings_uploads_an_avatar_via_data_uri(client: TestClient) -> None:
    headers = _register_and_auth_headers(client, email="avatar2@example.com")

    resp = client.patch(
        "/v1/me/settings",
        headers=headers,
        json={"avatar_base64": f"data:image/png;base64,{_PNG_BASE64}"},
    )
    assert resp.status_code == 200
    avatar_url = resp.json()["settings"]["avatar_url"]
    filename = avatar_url.removeprefix("/static/avatars/")
    (avatars_dir() / filename).unlink()


def test_re_uploading_an_avatar_deletes_the_old_file(client: TestClient) -> None:
    headers = _register_and_auth_headers(client, email="avatar3@example.com")

    first = client.patch(
        "/v1/me/settings", headers=headers, json={"avatar_base64": _PNG_BASE64}
    ).json()["settings"]["avatar_url"]
    first_path = avatars_dir() / first.removeprefix("/static/avatars/")
    assert first_path.exists()

    second = client.patch(
        "/v1/me/settings", headers=headers, json={"avatar_base64": _PNG_BASE64}
    ).json()["settings"]["avatar_url"]
    second_path = avatars_dir() / second.removeprefix("/static/avatars/")

    assert second != first  # a fresh random filename every upload
    assert not first_path.exists()  # the old one is gone
    assert second_path.exists()
    second_path.unlink()


def test_remove_avatar_clears_it_and_deletes_the_file(client: TestClient) -> None:
    headers = _register_and_auth_headers(client, email="avatar4@example.com")
    avatar_url = client.patch(
        "/v1/me/settings", headers=headers, json={"avatar_base64": _PNG_BASE64}
    ).json()["settings"]["avatar_url"]
    path = avatars_dir() / avatar_url.removeprefix("/static/avatars/")
    assert path.exists()

    resp = client.patch("/v1/me/settings", headers=headers, json={"remove_avatar": True})
    assert resp.status_code == 200
    assert resp.json()["settings"]["avatar_url"] is None
    assert not path.exists()


def test_patch_settings_rejects_a_non_image_upload(client: TestClient) -> None:
    headers = _register_and_auth_headers(client, email="avatar5@example.com")
    not_an_image = base64.b64encode(b"just some plain text, not an image").decode()

    resp = client.patch("/v1/me/settings", headers=headers, json={"avatar_base64": not_an_image})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "avatar.invalid_image"
    assert client.get("/v1/me", headers=headers).json()["settings"]["avatar_url"] is None


def test_patch_settings_rejects_an_oversized_avatar(client: TestClient) -> None:
    headers = _register_and_auth_headers(client, email="avatar6@example.com")
    oversized = b"\x89PNG\r\n\x1a\n" + b"\x00" * (get_settings().avatar_max_bytes + 1)
    too_large = base64.b64encode(oversized).decode()

    resp = client.patch("/v1/me/settings", headers=headers, json={"avatar_base64": too_large})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "avatar.too_large"


def test_deleting_the_account_leaves_its_avatar_file_for_now(client: TestClient) -> None:
    """DELETE /me is a soft delete (product decision) -- the row and
    everything it owns, including a photo on disk, stays physically
    untouched until Phase 2's scheduled purge actually runs. Only
    access to the account is what disappears immediately."""
    headers = _register_and_auth_headers(client, email="avatar7@example.com")
    avatar_url = client.patch(
        "/v1/me/settings", headers=headers, json={"avatar_base64": _PNG_BASE64}
    ).json()["settings"]["avatar_url"]
    path = avatars_dir() / avatar_url.removeprefix("/static/avatars/")
    assert path.exists()

    resp = client.delete("/v1/me", headers=headers)
    assert resp.status_code == 200
    assert path.exists()  # untouched -- not this endpoint's job
    path.unlink()  # test hygiene -- don't leave files behind


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


def test_put_balance_rejects_a_negative_amount(client: TestClient) -> None:
    headers = _register_and_auth_headers(client, email="negativebalance@example.com")

    resp = client.put(
        "/v1/me/balance",
        headers=headers,
        json={"current_balance_minor": -100, "balance_as_of": date.today().isoformat()},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "balance.negative_not_allowed"


def test_put_balance_accepts_zero(client: TestClient) -> None:
    headers = _register_and_auth_headers(client, email="zerobalance@example.com")

    resp = client.put(
        "/v1/me/balance",
        headers=headers,
        json={"current_balance_minor": 0, "balance_as_of": date.today().isoformat()},
    )
    assert resp.status_code == 200


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


def test_change_password_requires_auth(client: TestClient) -> None:
    resp = client.patch(
        "/v1/me/password", json={"current_password": "correct-horse", "new_password": "brand-new1"}
    )
    assert resp.status_code == 401


def test_change_password_succeeds_and_old_password_stops_working(client: TestClient) -> None:
    headers = _register_and_auth_headers(client, email="changepw@example.com")

    resp = client.patch(
        "/v1/me/password",
        headers=headers,
        json={"current_password": "correct-horse", "new_password": "brand-new-pw"},
    )
    assert resp.status_code == 200
    assert resp.json()["message_en"]
    assert resp.json()["message_ar"]

    old_login = client.post(
        "/v1/auth/login", json={"email": "changepw@example.com", "password": "correct-horse"}
    )
    assert old_login.status_code == 401

    new_login = client.post(
        "/v1/auth/login", json={"email": "changepw@example.com", "password": "brand-new-pw"}
    )
    assert new_login.status_code == 200


def test_change_password_wrong_current_password_is_rejected(client: TestClient) -> None:
    headers = _register_and_auth_headers(client, email="wrongcurrent@example.com")

    resp = client.patch(
        "/v1/me/password",
        headers=headers,
        json={"current_password": "not-the-real-one", "new_password": "brand-new-pw"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "auth.current_password_incorrect"

    # The password must be genuinely unchanged.
    still_works = client.post(
        "/v1/auth/login", json={"email": "wrongcurrent@example.com", "password": "correct-horse"}
    )
    assert still_works.status_code == 200


def test_change_password_weak_new_password_is_rejected(client: TestClient) -> None:
    headers = _register_and_auth_headers(client, email="weaknew@example.com")

    resp = client.patch(
        "/v1/me/password",
        headers=headers,
        json={"current_password": "correct-horse", "new_password": "short"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "auth.weak_password"


def test_change_password_revokes_other_sessions(client: TestClient) -> None:
    """Changing a password revokes every refresh-token family for the
    user, including the one that authenticated this very request -- the
    client is expected to re-authenticate afterward."""
    resp = client.post(
        "/v1/auth/register",
        json={"email": "revoke@example.com", "password": "correct-horse", "name": "Test User"},
    )
    tokens = resp.json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    client.patch(
        "/v1/me/password",
        headers=headers,
        json={"current_password": "correct-horse", "new_password": "brand-new-pw"},
    )

    refresh_resp = client.post("/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refresh_resp.status_code == 401
    assert refresh_resp.json()["error"]["code"] == "auth.token_invalid"
