"""The error envelope shape end to end over real HTTP: code, params and
request_id (pre-existing), plus message_en/message_ar (new). The
exhaustive per-code checks live in tests/core/test_bilingual_messages.py;
this just proves the wiring reaches an actual response for a
representative error and a representative action-success result.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.errors import ERROR_MESSAGES


def test_error_envelope_carries_bilingual_messages_matching_the_registry(
    client: TestClient,
) -> None:
    resp = client.post(
        "/v1/auth/login", json={"email": "nobody@example.com", "password": "wrong-one"}
    )
    assert resp.status_code == 401
    error = resp.json()["error"]
    assert error["code"] == "auth.invalid_credentials"
    expected_en, expected_ar = ERROR_MESSAGES["auth.invalid_credentials"]
    assert error["message_en"] == expected_en
    assert error["message_ar"] == expected_ar
    assert "request_id" in error
    assert error["params"] == {}


def test_action_result_carries_bilingual_messages(client: TestClient) -> None:
    resp = client.post(
        "/v1/auth/register",
        json={
            "email": "actionresult@example.com",
            "password": "correct-horse",
            "name": "Test User",
        },
    )
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    resp = client.delete("/v1/me/data", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"message_en", "message_ar"}
    assert body["message_en"]
    assert body["message_ar"]
