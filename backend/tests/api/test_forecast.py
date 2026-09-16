"""GET /scenarios/{id}/forecast and GET /forecast/compare, end to end
over real HTTP against the real test database.

The golden-fixture cases directly prove backend-plan/11's M5 done
criterion: a request through the actual HTTP API produces a ledger
matching the engine-level golden fixtures exactly -- proving the whole
chain (persistence -> resolution -> engine -> response shaping), not
just the engine in isolation, which M1 already covered thoroughly. Only
a representative subset runs here (the clamp rule, a multi-occurrence
recurrence, and the empty-scenario baseline) -- re-running all nine
would just re-prove the engine, which is not this layer's job.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

FIXTURES_DIR = Path(__file__).parent.parent / "engine" / "fixtures"
GOLDEN_CASES = [
    "m1/22.1.json",
    "m1/24.1.json",
    "m1/18.1.json",
]


def _auth_headers(client: TestClient, email: str = "fc@example.com") -> dict[str, str]:
    resp = client.post(
        "/v1/auth/register", json={"email": email, "password": "correct-horse", "name": "Test User"}
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _base_id(client: TestClient, headers: dict) -> str:
    return client.get("/v1/scenarios", headers=headers).json()["items"][0]["id"]


def _set_current_balance(client: TestClient, headers: dict, amount_minor: int) -> None:
    resp = client.put(
        "/v1/me/balance",
        headers=headers,
        json={"current_balance_minor": amount_minor, "balance_as_of": "2026-01-01"},
    )
    assert resp.status_code == 200


@pytest.mark.parametrize("fixture_name", GOLDEN_CASES)
def test_forecast_over_http_matches_engine_golden_fixture(
    client: TestClient, fixture_name: str
) -> None:
    case = json.loads((FIXTURES_DIR / fixture_name).read_text())
    safe_name = fixture_name.replace("/", "-")
    headers = _auth_headers(client, email=f"golden-{safe_name}@example.com")
    base_id = _base_id(client, headers)
    _set_current_balance(client, headers, case["current_balance_minor"])

    for txn in case["transactions"]:
        body = {
            "name": txn["name"],
            "amount_minor": txn["amount_minor"],
            "direction": txn["direction"],
            "recurrence": txn["recurrence"],
            "start_date": txn["start_date"],
            "end_date": txn.get("end_date"),
        }
        resp = client.post(f"/v1/scenarios/{base_id}/transactions", headers=headers, json=body)
        assert resp.status_code == 201, resp.text

    # The engine fixtures use short horizons for hand-computation convenience;
    # the API restricts horizon to {12, 36, 60, 120} (architecture §11.4).
    # Request the smallest allowed horizon that covers the fixture's own, and
    # compare only the months the fixture actually asserts -- the engine
    # computes each month sequentially from the Current Cash Balance forward, so a
    # longer window never changes the earlier months' values.
    api_horizon = next(h for h in (12, 36, 60, 120) if h >= case["horizon_months"])
    resp = client.get(
        f"/v1/scenarios/{base_id}/forecast",
        headers=headers,
        params={"horizon": api_horizon, "anchor": case["anchor_month"]},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["current_balance_minor"] == case["current_balance_minor"]
    assert body["anchor_month"] == case["anchor_month"]
    covered_months = body["months"][: len(case["expected_months"])]
    for actual, expected in zip(covered_months, case["expected_months"], strict=True):
        assert actual["month"] == expected["month"], case["name"]
        assert actual["income_minor"] == expected["income_minor"], case["name"]
        assert actual["expense_minor"] == expected["expense_minor"], case["name"]
        assert actual["net_minor"] == expected["net_minor"], case["name"]
        assert actual["closing_balance_minor"] == expected["closing_balance_minor"], case["name"]


def test_forecast_default_currency_is_sar(client: TestClient) -> None:
    headers = _auth_headers(client, email="currency@example.com")
    base_id = _base_id(client, headers)
    resp = client.get(f"/v1/scenarios/{base_id}/forecast", headers=headers, params={"horizon": 12})
    assert resp.status_code == 200
    assert resp.json()["currency_code"] == "SAR"


def test_forecast_reflects_changed_currency(client: TestClient) -> None:
    headers = _auth_headers(client, email="currency2@example.com")
    base_id = _base_id(client, headers)
    client.patch("/v1/me/settings", headers=headers, json={"currency_code": "USD"})
    resp = client.get(f"/v1/scenarios/{base_id}/forecast", headers=headers, params={"horizon": 12})
    assert resp.json()["currency_code"] == "USD"


def test_forecast_uses_scenario_current_balance_override(client: TestClient) -> None:
    headers = _auth_headers(client, email="override@example.com")
    _set_current_balance(client, headers, 100000)
    plan = client.post(
        "/v1/scenarios",
        headers=headers,
        json={"name": "Buy House", "current_balance_override_minor": 999999},
    ).json()

    resp = client.get(
        f"/v1/scenarios/{plan['id']}/forecast", headers=headers, params={"horizon": 12}
    )
    assert resp.json()["current_balance_minor"] == 999999


def test_forecast_falls_back_to_settings_when_no_override(client: TestClient) -> None:
    headers = _auth_headers(client, email="nooverride@example.com")
    _set_current_balance(client, headers, 555000)
    base_id = _base_id(client, headers)

    resp = client.get(f"/v1/scenarios/{base_id}/forecast", headers=headers, params={"horizon": 12})
    assert resp.json()["current_balance_minor"] == 555000


def test_forecast_horizon_outside_range_is_rejected(client: TestClient) -> None:
    """architecture §11.4: the endpoint accepts any value in
    [1, max_horizon_months], not just the four client-facing presets --
    the dashboard needs months_elapsed + 12, which usually isn't one of
    them. Only genuinely out-of-range values are rejected."""
    headers = _auth_headers(client, email="badhorizon@example.com")
    base_id = _base_id(client, headers)

    resp = client.get(f"/v1/scenarios/{base_id}/forecast", headers=headers, params={"horizon": 0})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "forecast.invalid_horizon"

    resp = client.get(f"/v1/scenarios/{base_id}/forecast", headers=headers, params={"horizon": 121})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "forecast.invalid_horizon"


def test_forecast_horizon_not_one_of_the_four_presets_is_accepted(client: TestClient) -> None:
    headers = _auth_headers(client, email="oddhorizon@example.com")
    base_id = _base_id(client, headers)

    resp = client.get(f"/v1/scenarios/{base_id}/forecast", headers=headers, params={"horizon": 17})
    assert resp.status_code == 200
    assert resp.json()["horizon_months"] == 17


def test_forecast_explicit_anchor_is_reproducible(client: TestClient) -> None:
    headers = _auth_headers(client, email="reproducible@example.com")
    base_id = _base_id(client, headers)
    params = {"horizon": 12, "anchor": "2027-03"}

    first = client.get(f"/v1/scenarios/{base_id}/forecast", headers=headers, params=params)
    second = client.get(f"/v1/scenarios/{base_id}/forecast", headers=headers, params=params)
    assert first.json() == second.json()
    assert first.json()["anchor_month"] == "2027-03"


def test_forecast_anchor_defaults_to_balance_as_of_not_today(client: TestClient) -> None:
    """architecture §7.1/build spec §11.4: an omitted anchor defaults to
    the month of balance_as_of, which may be in the past -- never to
    today's device/server clock."""
    headers = _auth_headers(client, email="anchordefault@example.com")
    _set_current_balance(client, headers, 100000)  # sets balance_as_of to 2026-01-01
    base_id = _base_id(client, headers)

    resp = client.get(f"/v1/scenarios/{base_id}/forecast", headers=headers, params={"horizon": 12})
    body = resp.json()
    assert body["anchor_month"] == "2026-01"
    assert body["balance_as_of"] == "2026-01-01"


def test_forecast_current_month_and_months_elapsed(client: TestClient) -> None:
    """architecture §7.5: current_month/months_elapsed position "today"
    within the returned rows, so the client never derives either from
    its own device clock."""
    headers = _auth_headers(client, email="elapsed@example.com")
    _set_current_balance(client, headers, 100000)  # balance_as_of = 2026-01-01
    base_id = _base_id(client, headers)

    resp = client.get(f"/v1/scenarios/{base_id}/forecast", headers=headers, params={"horizon": 12})
    body = resp.json()
    assert "current_month" in body
    assert "months_elapsed" in body
    # anchor_month -> current_month, in months -- must agree with the two
    # ISO month strings the response itself carries, not a hardcoded value
    # (this test doesn't control what "today" is).
    anchor_year, anchor_month_num = (int(p) for p in body["anchor_month"].split("-"))
    current_year, current_month_num = (int(p) for p in body["current_month"].split("-"))
    expected_elapsed = (current_year * 12 + current_month_num) - (
        anchor_year * 12 + anchor_month_num
    )
    assert body["months_elapsed"] == expected_elapsed


def test_forecast_not_found_for_another_users_scenario(client: TestClient) -> None:
    headers_a = _auth_headers(client, email="fowner@example.com")
    headers_b = _auth_headers(client, email="fintruder@example.com")
    base_id_a = _base_id(client, headers_a)

    resp = client.get(
        f"/v1/scenarios/{base_id_a}/forecast", headers=headers_b, params={"horizon": 12}
    )
    assert resp.status_code == 404


def test_forecast_requires_auth(client: TestClient) -> None:
    headers = _auth_headers(client, email="fnoauth@example.com")
    base_id = _base_id(client, headers)
    resp = client.get(f"/v1/scenarios/{base_id}/forecast", params={"horizon": 12})
    assert resp.status_code == 401


def test_compare_same_scenario_is_rejected(client: TestClient) -> None:
    headers = _auth_headers(client, email="samecmp@example.com")
    base_id = _base_id(client, headers)
    resp = client.get(
        "/v1/forecast/compare", headers=headers, params={"a": base_id, "b": base_id, "horizon": 12}
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "compare.same_scenario"


def test_compare_omitted_anchor_defaults_identically_for_both_sides(client: TestClient) -> None:
    """D-14: balance_as_of is user-level, not per-scenario, so an omitted
    anchor must default to the same month on both sides of a compare --
    never two independent clock reads that could straddle a boundary."""
    headers = _auth_headers(client, email="cmpanchor@example.com")
    _set_current_balance(client, headers, 100000)  # balance_as_of = 2026-01-01
    base_id = _base_id(client, headers)
    plan = client.post("/v1/scenarios", headers=headers, json={"name": "Side Income"}).json()

    resp = client.get(
        "/v1/forecast/compare",
        headers=headers,
        params={"a": base_id, "b": plan["id"], "horizon": 12},
    )
    body = resp.json()
    assert body["a"]["anchor_month"] == "2026-01"
    assert body["b"]["anchor_month"] == "2026-01"


def test_compare_base_against_derived_scenario_drivers_and_deltas(client: TestClient) -> None:
    headers = _auth_headers(client, email="cmp@example.com")
    base_id = _base_id(client, headers)
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
    client.post(
        f"/v1/scenarios/{plan['id']}/transactions",
        headers=headers,
        json={
            "name": "Mortgage",
            "amount_minor": 200000,
            "direction": "expense",
            "recurrence": "monthly",
            "start_date": "2026-01-01",
        },
    )

    resp = client.get(
        "/v1/forecast/compare",
        headers=headers,
        params={"a": base_id, "b": plan["id"], "horizon": 12, "anchor": "2026-01"},
    )
    assert resp.status_code == 200
    body = resp.json()

    assert body["a"]["scenario_id"] == base_id
    assert body["b"]["scenario_id"] == plan["id"]
    assert len(body["deltas"]) == 12

    drivers_by_name = {d["name"]: d for d in body["drivers"]}
    assert drivers_by_name["Rent"]["change"] == "modified"
    assert (
        drivers_by_name["Rent"]["total_contribution_minor"] == -50000 * 12
    )  # 50000/mo more expense
    assert drivers_by_name["Rent"]["active_months"] == 12  # present the whole horizon
    assert drivers_by_name["Mortgage"]["change"] == "added"
    assert drivers_by_name["Mortgage"]["direction"] == "expense"
    assert drivers_by_name["Mortgage"]["active_months"] == 12

    total_contribution = sum(d["total_contribution_minor"] for d in body["drivers"])
    actual_delta = (
        body["b"]["totals"]["closing_balance_minor"] - body["a"]["totals"]["closing_balance_minor"]
    )
    assert total_contribution == actual_delta


def test_compare_driver_active_months_reflects_a_mid_horizon_start(client: TestClient) -> None:
    """A client computes a driver's real "$X/mo" as
    total_contribution_minor / active_months -- never / horizon_months,
    which would dilute anything that doesn't span the whole comparison
    window (e.g. an item added partway through)."""
    headers = _auth_headers(client, email="cmpmonths@example.com")
    base_id = _base_id(client, headers)
    plan = client.post("/v1/scenarios", headers=headers, json={"name": "Buy House"}).json()
    client.post(
        f"/v1/scenarios/{plan['id']}/transactions",
        headers=headers,
        json={
            "name": "Mortgage",
            "amount_minor": 90000,
            "direction": "expense",
            "recurrence": "monthly",
            "start_date": "2026-03-01",  # 2 months into a 6-month horizon
        },
    )

    resp = client.get(
        "/v1/forecast/compare",
        headers=headers,
        params={"a": base_id, "b": plan["id"], "horizon": 6, "anchor": "2026-01"},
    )
    assert resp.status_code == 200
    mortgage = next(d for d in resp.json()["drivers"] if d["name"] == "Mortgage")

    assert mortgage["active_months"] == 4  # Mar/Apr/May/Jun -- not the full 6-month horizon
    assert mortgage["total_contribution_minor"] == -90000 * 4
    assert mortgage["total_contribution_minor"] / mortgage["active_months"] == -90000


def test_compare_percentage_is_none_when_baseline_month_is_zero(client: TestClient) -> None:
    headers = _auth_headers(client, email="cmppct@example.com")
    # Current Cash Balance 0, no transactions -> every month is 0
    base_id = _base_id(client, headers)
    plan = client.post("/v1/scenarios", headers=headers, json={"name": "Side Income"}).json()
    client.post(
        f"/v1/scenarios/{plan['id']}/transactions",
        headers=headers,
        json={
            "name": "Bonus",
            "amount_minor": 10000,
            "direction": "income",
            "recurrence": "one_time",
            "start_date": "2026-01-01",
        },
    )

    resp = client.get(
        "/v1/forecast/compare",
        headers=headers,
        params={"a": base_id, "b": plan["id"], "horizon": 12, "anchor": "2026-01"},
    )
    assert resp.json()["deltas"][0]["closing_balance_delta_pct"] is None


def test_compare_requires_auth(client: TestClient) -> None:
    headers = _auth_headers(client, email="cmpnoauth@example.com")
    base_id = _base_id(client, headers)
    plan = client.post("/v1/scenarios", headers=headers, json={"name": "Other"}).json()
    resp = client.get("/v1/forecast/compare", params={"a": base_id, "b": plan["id"], "horizon": 12})
    assert resp.status_code == 401
