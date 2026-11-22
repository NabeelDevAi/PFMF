"""GET /scenarios/{id}/forecast and /forecast/compare with `until` (UAT-005)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _auth_headers(client: TestClient, email: str = "until@example.com") -> dict[str, str]:
    resp = client.post(
        "/v1/auth/register", json={"email": email, "password": "correct-horse", "name": "Test User"}
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _base_id(client: TestClient, headers: dict) -> str:
    items = client.get("/v1/scenarios", headers=headers).json()["items"]
    return next(s["id"] for s in items if s["is_base"])


def _add(client: TestClient, headers: dict, scenario_id: str, **body) -> None:
    resp = client.post(f"/v1/scenarios/{scenario_id}/transactions", headers=headers, json=body)
    assert resp.status_code == 201, resp.text


def _setup(client: TestClient, email: str) -> tuple[dict, str]:
    headers = _auth_headers(client, email)
    base_id = _base_id(client, headers)
    _add(
        client,
        headers,
        base_id,
        name="Salary",
        amount_minor=500000,
        direction="income",
        recurrence="monthly",
        start_date="2026-01-25",
    )
    _add(
        client,
        headers,
        base_id,
        name="Rent",
        amount_minor=300000,
        direction="expense",
        recurrence="monthly",
        start_date="2026-01-01",
    )
    return headers, base_id


def _forecast(client: TestClient, headers: dict, sid: str, **params):
    return client.get(
        f"/v1/scenarios/{sid}/forecast", headers=headers, params={"anchor": "2026-01", **params}
    )


def test_until_mid_month_cuts_the_last_month(client: TestClient) -> None:
    headers, sid = _setup(client, "u1@example.com")
    resp = _forecast(client, headers, sid, until="2026-03-10", include_occurrences=True)
    assert resp.status_code == 200
    body = resp.json()
    assert [m["month"] for m in body["months"]] == ["2026-01", "2026-02", "2026-03"]
    assert body["horizon_months"] == 3
    assert body["until"] == "2026-03-10"
    assert max(o["on"] for o in body["occurrences"]) <= "2026-03-10"
    march = body["months"][2]
    assert (march["income_minor"], march["expense_minor"]) == (0, 300000)


def test_until_on_a_month_end_matches_the_equivalent_horizon(client: TestClient) -> None:
    headers, sid = _setup(client, "u2@example.com")
    by_until = _forecast(client, headers, sid, until="2026-06-30").json()
    by_horizon = _forecast(client, headers, sid, horizon=6).json()
    assert by_until["months"] == by_horizon["months"]
    assert by_until["totals"] == by_horizon["totals"]
    assert by_until["until"] == by_horizon["until"] == "2026-06-30"


def test_horizon_response_reports_the_last_day_of_the_final_month(client: TestClient) -> None:
    headers, sid = _setup(client, "u3@example.com")
    assert _forecast(client, headers, sid, horizon=2).json()["until"] == "2026-02-28"
    assert _forecast(client, headers, sid, horizon=12).json()["until"] == "2026-12-31"


def test_until_on_the_first_day_of_the_anchor_month_is_valid(client: TestClient) -> None:
    headers, sid = _setup(client, "u4@example.com")
    resp = _forecast(client, headers, sid, until="2026-01-01")
    assert resp.status_code == 200
    assert len(resp.json()["months"]) == 1


def test_until_before_the_anchor_month_is_rejected(client: TestClient) -> None:
    headers, sid = _setup(client, "u5@example.com")
    resp = _forecast(client, headers, sid, until="2025-12-31")
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "forecast.invalid_until"


def test_until_beyond_the_ten_year_limit_is_rejected_and_the_limit_is_accepted(
    client: TestClient,
) -> None:
    headers, sid = _setup(client, "u6@example.com")
    # anchor 2026-01 + 120 months ends 2035-12-31.
    ok = _forecast(client, headers, sid, until="2035-12-31")
    assert ok.status_code == 200
    assert len(ok.json()["months"]) == 120
    too_far = _forecast(client, headers, sid, until="2036-01-01")
    assert too_far.status_code == 422
    assert too_far.json()["error"]["code"] == "forecast.invalid_until"


def test_exactly_one_of_horizon_and_until_is_required(client: TestClient) -> None:
    headers, sid = _setup(client, "u7@example.com")
    both = _forecast(client, headers, sid, horizon=6, until="2026-06-30")
    assert both.status_code == 422
    assert both.json()["error"]["code"] == "validation.invalid"
    neither = _forecast(client, headers, sid)
    assert neither.status_code == 422
    assert neither.json()["error"]["code"] == "validation.invalid"


def test_until_with_a_malformed_date_is_rejected(client: TestClient) -> None:
    headers, sid = _setup(client, "u8@example.com")
    assert _forecast(client, headers, sid, until="30-11-2027").status_code == 422


def test_horizon_behaviour_is_unchanged(client: TestClient) -> None:
    headers, sid = _setup(client, "u9@example.com")
    assert _forecast(client, headers, sid, horizon=0).json()["error"]["code"] == (
        "forecast.invalid_horizon"
    )
    assert _forecast(client, headers, sid, horizon=121).json()["error"]["code"] == (
        "forecast.invalid_horizon"
    )
    assert len(_forecast(client, headers, sid, horizon=120).json()["months"]) == 120


def test_compare_with_until_uses_the_same_window_for_both_plans(client: TestClient) -> None:
    headers, base_id = _setup(client, "u10@example.com")
    plan = client.post("/v1/scenarios", headers=headers, json={"name": ["Car"]}).json()["items"][0]
    _add(
        client,
        headers,
        plan["id"],
        name="Car payment",
        amount_minor=150000,
        direction="expense",
        recurrence="monthly",
        start_date="2026-01-10",
    )

    resp = client.get(
        "/v1/forecast/compare",
        headers=headers,
        params={"a": base_id, "b": plan["id"], "until": "2026-03-15", "anchor": "2026-01"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["a"]["until"] == body["b"]["until"] == "2026-03-15"
    assert len(body["a"]["months"]) == len(body["b"]["months"]) == 3
    # March is cut on the 15th, so the car payment (10th) counts there too.
    assert [d["net_delta_minor"] for d in body["deltas"]] == [-150000, -150000, -150000]


def test_compare_requires_exactly_one_of_horizon_and_until(client: TestClient) -> None:
    headers, base_id = _setup(client, "u11@example.com")
    plan = client.post("/v1/scenarios", headers=headers, json={"name": ["Other"]}).json()["items"][
        0
    ]
    params = {"a": base_id, "b": plan["id"], "anchor": "2026-01"}
    assert client.get("/v1/forecast/compare", headers=headers, params=params).status_code == 422
    both = client.get(
        "/v1/forecast/compare",
        headers=headers,
        params={**params, "horizon": 6, "until": "2026-06-30"},
    )
    assert both.status_code == 422


def test_until_requires_authentication_and_respects_ownership(client: TestClient) -> None:
    headers, sid = _setup(client, "u12@example.com")
    other = _auth_headers(client, "u12b@example.com")
    assert _forecast(client, other, sid, until="2026-03-10").status_code == 404
    unauth = client.get(
        f"/v1/scenarios/{sid}/forecast", params={"until": "2026-03-10", "anchor": "2026-01"}
    )
    assert unauth.status_code == 401
