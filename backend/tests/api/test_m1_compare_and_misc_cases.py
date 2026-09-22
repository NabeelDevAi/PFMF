"""M1 cases 26.1-26.3 (comparison), 27.3 (dashboard periods), and 28.1
(currency) -- backend-plan/12 §6 item 9, Part B.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.api._m1_helpers import (
    base_plan_expected_months,
    create_plan,
    forecast,
    register,
    setup_base_plan,
)


def _build_base_and_buy_house(client: TestClient, email: str) -> tuple[dict, dict, dict]:
    headers = register(client, email)
    plan = setup_base_plan(client, headers)
    buy_house = create_plan(client, headers, "Buy House")
    client.post(
        f"/v1/scenarios/{buy_house['id']}/overlays",
        headers=headers,
        json={
            "base_transaction_id": plan["rent_id"],
            "op": "override",
            "ovr_end_date": "2026-05-31",
        },
    )
    client.post(
        f"/v1/scenarios/{buy_house['id']}/transactions",
        headers=headers,
        json={
            "name": "Mortgage",
            "amount_minor": 650_000,
            "direction": "expense",
            "recurrence": "monthly",
            "start_date": "2026-06-01",
        },
    )
    return headers, plan, buy_house


def test_m1_case_26_1_comparing_base_plan_against_buy_house(client: TestClient) -> None:
    headers, plan, buy_house = _build_base_and_buy_house(client, "m1-26-1@example.com")

    resp = client.get(
        "/v1/forecast/compare",
        headers=headers,
        params={"a": plan["base_id"], "b": buy_house["id"], "horizon": 12},
    )
    assert resp.status_code == 200
    body = resp.json()
    deltas = {d["month"]: d for d in body["deltas"]}

    assert deltas["2026-01"]["closing_balance_delta_minor"] == 0
    assert deltas["2026-05"]["closing_balance_delta_minor"] == 0
    assert deltas["2026-06"]["closing_balance_delta_minor"] == -200_000  # -2,000
    assert deltas["2026-07"]["closing_balance_delta_minor"] == -400_000  # -4,000

    dec = deltas["2026-12"]
    assert dec["closing_balance_delta_minor"] == -1_400_000  # -14,000
    assert dec["closing_balance_delta_pct"] == -4.98


def test_m1_case_26_2_what_is_driving_the_difference(client: TestClient) -> None:
    headers, plan, buy_house = _build_base_and_buy_house(client, "m1-26-2@example.com")

    body = client.get(
        "/v1/forecast/compare",
        headers=headers,
        params={"a": plan["base_id"], "b": buy_house["id"], "horizon": 12},
    ).json()
    drivers = {d["name"]: d for d in body["drivers"]}

    assert set(drivers) == {"Mortgage", "Rent"}  # Salary/Utilities unchanged -- not listed
    assert drivers["Mortgage"]["change"] == "added"
    assert drivers["Mortgage"]["total_contribution_minor"] == -4_550_000  # -45,500
    assert drivers["Rent"]["change"] == "modified"
    assert drivers["Rent"]["total_contribution_minor"] == 3_150_000  # +31,500

    # The contributions must add up exactly to the total difference (also check 29.4).
    total_contribution = sum(d["total_contribution_minor"] for d in body["drivers"])
    assert total_contribution == -1_400_000  # -14,000


def test_m1_case_26_3_percentage_where_the_baseline_is_zero(client: TestClient) -> None:
    headers = register(client, "m1-26-3@example.com")
    base_id = client.get("/v1/scenarios", headers=headers).json()["items"][0]["id"]
    # Base has zero balance and zero items by default (fresh registration)
    # -- an empty ledger, so every month's closing balance is exactly 0.
    plan_b = create_plan(client, headers, "Plan B")
    resp = client.post(
        f"/v1/scenarios/{plan_b['id']}/transactions",
        headers=headers,
        json={
            "name": "Windfall",
            "amount_minor": 500_000,
            "direction": "income",
            "recurrence": "one_time",
            "start_date": "2026-01-15",
        },
    )
    assert resp.status_code == 201

    body = client.get(
        "/v1/forecast/compare",
        headers=headers,
        params={"a": base_id, "b": plan_b["id"], "horizon": 1, "anchor": "2026-01"},
    ).json()
    delta = body["deltas"][0]
    assert delta["closing_balance_delta_minor"] == 500_000
    assert delta["closing_balance_delta_pct"] is None  # never 0% or an error


def test_m1_case_27_3_dashboard_selected_period_totals(client: TestClient) -> None:
    """Every period total is a client-side sum of the same forecast
    payload's monthly rows -- this test proves those sums agree with
    the doc's own stated period figures, and that the Current Cash
    Balance never responds to the period selector (R32)."""
    headers = register(client, "m1-27-3@example.com")
    plan = setup_base_plan(client, headers)

    body = forecast(client, headers, plan["base_id"], horizon=12)
    months = body["months"]
    expected_closing = base_plan_expected_months()

    periods = {
        1: (2_500_000, 530_000, 1_970_000, expected_closing[0]),  # this month
        3: (7_500_000, 1_590_000, 5_910_000, expected_closing[2]),  # next 3 months
        6: (15_000_000, 3_180_000, 11_820_000, expected_closing[5]),  # next 6 months
        12: (30_000_000, 6_360_000, 23_640_000, expected_closing[11]),  # next 12 months
    }
    for n, (income, expense, net, closing) in periods.items():
        window = months[:n]
        assert sum(m["income_minor"] for m in window) == income
        assert sum(m["expense_minor"] for m in window) == expense
        assert sum(m["net_minor"] for m in window) == net
        assert window[-1]["closing_balance_minor"] == closing

    # The Current Cash Balance is the same figure regardless of period.
    assert body["current_balance_minor"] == 4_500_000
    assert body["balance_as_of"] == "2026-01-01"


def test_m1_case_28_1_changing_currency_does_not_convert_amounts(client: TestClient) -> None:
    headers = register(client, "m1-28-1@example.com")
    plan = setup_base_plan(client, headers)

    before = forecast(client, headers, plan["base_id"], horizon=12)
    assert before["currency_code"] == "SAR"
    assert before["months"][-1]["closing_balance_minor"] == 28_140_000

    resp = client.patch("/v1/me/settings", headers=headers, json={"currency_code": "USD"})
    assert resp.status_code == 200
    assert resp.json()["settings"]["currency_code"] == "USD"

    after = forecast(client, headers, plan["base_id"], horizon=12)
    assert after["currency_code"] == "USD"
    # Every numeric value is identical -- only the currency label changed.
    assert after["current_balance_minor"] == before["current_balance_minor"]
    assert after["months"] == before["months"]
    assert after["totals"] == before["totals"]
