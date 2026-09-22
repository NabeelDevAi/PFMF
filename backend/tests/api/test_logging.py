"""Structured logging (Tier 2 #11): request-id correlation, and the fix
for the specific gap that motivated this -- an unhandled exception used
to disappear into a generic 500 with zero server-side trace."""

from __future__ import annotations

import json
import logging

from fastapi.testclient import TestClient


def test_every_response_carries_an_x_request_id_header(client: TestClient) -> None:
    resp = client.get("/v1/health")
    assert "X-Request-Id" in resp.headers


def test_access_log_line_is_emitted_and_correlated_to_the_response_header(
    client: TestClient, caplog
) -> None:
    with caplog.at_level(logging.INFO, logger="pfmf.access"):
        resp = client.get("/v1/health")

    access_records = [r for r in caplog.records if r.name == "pfmf.access"]
    assert len(access_records) == 1
    record = access_records[0]
    assert record.request_id == resp.headers["X-Request-Id"]
    assert record.method == "GET"
    assert record.path == "/v1/health"
    assert record.status_code == 200


def test_login_failure_is_logged_without_the_attempted_email(client: TestClient, caplog) -> None:
    with caplog.at_level(logging.WARNING, logger="pfmf.auth"):
        client.post("/v1/auth/login", json={"email": "nobody@example.com", "password": "wrong1234"})

    auth_records = [r for r in caplog.records if r.name == "pfmf.auth"]
    assert any(r.getMessage() == "login failed" for r in auth_records)
    for record in auth_records:
        assert "nobody@example.com" not in json.dumps(record.__dict__, default=str)


def test_unhandled_exception_is_logged_with_a_traceback_not_silently_swallowed(
    client: TestClient, monkeypatch, caplog
) -> None:
    """The specific gap this item fixed: previously, anything that wasn't
    a deliberate APIError produced a 500 with no server-side record at
    all of what actually broke."""
    from app.services import settings_service as settings_service_module

    def _boom(self, user_id):
        raise RuntimeError("boom -- deliberately injected for this test")

    monkeypatch.setattr(settings_service_module.SettingsService, "get", _boom)

    registered = client.post(
        "/v1/auth/register",
        json={"email": "logboom@example.com", "password": "correct-horse", "name": "Test User"},
    )
    headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}

    # TestClient's default raise_server_exceptions=True re-raises a server
    # error into the test process regardless of a registered handler --
    # useful for catching accidental 500s during test-writing, but it
    # bypasses the exact thing this test wants to exercise: the real
    # production behavior (uvicorn), where the handler runs and a 500
    # response comes back rather than the exception propagating.
    no_raise_client = TestClient(client.app, raise_server_exceptions=False)
    with caplog.at_level(logging.ERROR, logger="pfmf.errors"):
        resp = no_raise_client.get("/v1/me", headers=headers)

    assert resp.status_code == 500
    assert resp.json()["error"]["code"] == "internal"

    error_records = [r for r in caplog.records if r.name == "pfmf.errors"]
    assert len(error_records) == 1
    assert error_records[0].exc_info is not None
    assert "boom -- deliberately injected for this test" in caplog.text
