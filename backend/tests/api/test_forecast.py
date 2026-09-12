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
    "monthly_clamps_to_month_end.json",
    "weekly_across_five_payday_month.json",
    "empty_scenario_produces_flat_ledger.json",
]


def _auth_headers(client: TestClient, email: str = "fc@example.com") -> dict[str, str]:
    resp = client.post("/v1/auth/register", json={"email": email, "password": "correct-horse"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _base_id(client: TestClient, headers: dict) -> str:
    return client.get("/v1/scenarios", headers=headers).json()["items"][0]["id"]


def _set_opening_balance(client: TestClient, headers: dict, amount_minor: int) -> None:
    resp = client.patch(
        "/v1/me/settings",
        headers=headers,
        json={"opening_balance_minor": amount_minor, "opening_balance_date": "2026-01-01"},
    )
    assert resp.status_code == 200


@pytest.mark.parametrize("fixture_name", GOLDEN_CASES)
def test_forecast_over_http_matches_engine_golden_fixture(
    client: TestClient, fixture_name: str
) -> None:
    case = json.loads((FIXTURES_DIR / fixture_name).read_text())
    headers = _auth_headers(client, email=f"golden-{fixture_name}@example.com")
    base_id = _base_id(client, headers)
    _set_opening_balance(client, headers, case["opening_balance_minor"])

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
    # computes each month sequentially from opening balance forward, so a
    # longer window never changes the earlier months' values.
    api_horizon = next(h for h in (12, 36, 60, 120) if h >= case["horizon_months"])
    resp = client.get(
        f"/v1/scenarios/{base_id}/forecast",
        headers=headers,
        params={"horizon": api_horizon, "anchor": case["anchor_month"]},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["opening_balance_minor"] == case["opening_balance_minor"]
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


def test_forecast_uses_scenario_opening_balance_override(client: TestClient) -> None:
    headers = _auth_headers(client, email="override@example.com")
    _set_opening_balance(client, headers, 100000)
    plan = client.post(
        "/v1/scenarios",
        headers=headers,
        json={"name": "Buy House", "opening_balance_override_minor": 999999},
    ).json()

    resp = client.get(
        f"/v1/scenarios/{plan['id']}/forecast", headers=headers, params={"horizon": 12}
    )
    assert resp.json()["opening_balance_minor"] == 999999


def test_forecast_falls_back_to_settings_when_no_override(client: TestClient) -> None:
    headers = _auth_headers(client, email="nooverride@example.com")
    _set_opening_balance(client, headers, 555000)
    base_id = _base_id(client, headers)

    resp = client.get(f"/v1/scenarios/{base_id}/forecast", headers=headers, params={"horizon": 12})
    assert resp.json()["opening_balance_minor"] == 555000


def test_forecast_invalid_horizon_is_rejected(client: TestClient) -> None:
    headers = _auth_headers(client, email="badhorizon@example.com")
    base_id = _base_id(client, headers)
    resp = client.get(f"/v1/scenarios/{base_id}/forecast", headers=headers, params={"horizon": 24})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "forecast.invalid_horizon"


def test_forecast_explicit_anchor_is_reproducible(client: TestClient) -> None:
    headers = _auth_headers(client, email="reproducible@example.com")
    base_id = _base_id(client, headers)
    params = {"horizon": 12, "anchor": "2027-03"}

    first = client.get(f"/v1/scenarios/{base_id}/forecast", headers=headers, params=params)
    second = client.get(f"/v1/scenarios/{base_id}/forecast", headers=headers, params=params)
    assert first.json() == second.json()
    assert first.json()["anchor_month"] == "2027-03"


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
    assert drivers_by_name["Mortgage"]["change"] == "added"
    assert drivers_by_name["Mortgage"]["direction"] == "expense"

    total_contribution = sum(d["total_contribution_minor"] for d in body["drivers"])
    actual_delta = (
        body["b"]["totals"]["closing_balance_minor"] - body["a"]["totals"]["closing_balance_minor"]
    )
    assert total_contribution == actual_delta


def test_compare_percentage_is_none_when_baseline_month_is_zero(client: TestClient) -> None:
    headers = _auth_headers(client, email="cmppct@example.com")
    base_id = _base_id(client, headers)  # opening balance 0, no transactions -> every month is 0
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
