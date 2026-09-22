"""M1 §18 cases 18.3-18.5 (backend-plan/12 §6 item 9, Part B): the
Current Cash Balance / Projected Balance separation (D-04), end to end
over real HTTP. §18.1-18.2 are pure-engine cases already covered by
tests/engine/fixtures/m1/18.1.json and 18.2.json.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.api._m1_helpers import forecast, register, setup_base_plan


def test_m1_case_18_3_current_balance_is_not_changed_by_scheduled_items(client: TestClient) -> None:
    """Even though every item's date has already passed by the "today"
    M1 states for this case (26-01-2026), the Current Cash Balance must
    still read exactly 45,000 as of 01-01-2026 -- nothing in the system
    ever mutates it. Projected Balance at the end of January is 64,700,
    a separate figure."""
    headers = register(client, "m1-18-3@example.com")
    plan = setup_base_plan(client, headers)

    body = forecast(client, headers, plan["base_id"], horizon=1)
    assert body["current_balance_minor"] == 4_500_000
    assert body["balance_as_of"] == "2026-01-01"
    assert body["months"][0]["month"] == "2026-01"
    assert body["months"][0]["closing_balance_minor"] == 6_470_000


def test_m1_case_18_4_updating_balance_reanchors_the_forecast(client: TestClient) -> None:
    headers = register(client, "m1-18-4@example.com")
    plan = setup_base_plan(client, headers)

    resp = client.put(
        "/v1/me/balance",
        headers=headers,
        json={"current_balance_minor": 15_000_000, "balance_as_of": "2026-06-01"},
    )
    assert resp.status_code == 200

    body = forecast(client, headers, plan["base_id"], horizon=7, anchor="2026-06")
    assert body["balance_as_of"] == "2026-06-01"
    assert body["months"][0]["month"] == "2026-06"
    assert body["months"][0]["closing_balance_minor"] == 16_970_000  # 169,700
    assert body["months"][-1]["month"] == "2026-12"
    assert body["months"][-1]["closing_balance_minor"] == 28_790_000  # 287,900


def test_m1_case_18_5_stale_balance_leaves_the_anchor_untouched(client: TestClient) -> None:
    """No balance update happens in this case -- the forecast stays
    anchored to January 2026 regardless of how much later "today" is."""
    headers = register(client, "m1-18-5@example.com")
    plan = setup_base_plan(client, headers)

    body = forecast(client, headers, plan["base_id"], horizon=6)
    assert body["current_balance_minor"] == 4_500_000
    assert body["balance_as_of"] == "2026-01-01"
    assert body["anchor_month"] == "2026-01"
    assert body["months"][-1]["month"] == "2026-06"
    assert body["months"][-1]["closing_balance_minor"] == 16_320_000  # 163,200
