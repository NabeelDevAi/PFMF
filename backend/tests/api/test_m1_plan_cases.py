"""M1 §25 cases 25.1-25.17 (backend-plan/12 §6 item 9, Part B): the
shared Base Plan, walked through plan creation, field-level overrides,
Base-delete cascades, archive/restore and duplicate, asserting the
doc's own December 2026 figures at each step. Each case builds its own
fresh Base Plan (see tests/api/_m1_helpers.py's module docstring for why
that's the faithful reading of how the doc scopes these cases, not a
simplification).

Case 25.11 is the most important one in this file: it is the specific
number (310,400, not 312,900) that catches a whole-row-snapshot bug in
field-level overlay resolution.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.api._m1_helpers import (
    base_plan_expected_months,
    by_name,
    create_plan,
    december_2026_closing,
    forecast,
    register,
    resolved_transactions,
    setup_base_plan,
)


def test_m1_case_25_1_base_plan_result(client: TestClient) -> None:
    headers = register(client, "m1-25-1@example.com")
    plan = setup_base_plan(client, headers)

    body = forecast(client, headers, plan["base_id"], horizon=12)
    actual = [m["closing_balance_minor"] for m in body["months"]]
    assert actual == base_plan_expected_months()
    assert actual[-1] == 28_140_000  # 281,400


def test_m1_case_25_2_a_new_plan_with_nothing_changed(client: TestClient) -> None:
    headers = register(client, "m1-25-2@example.com")
    plan = setup_base_plan(client, headers)
    test_plan = create_plan(client, headers, "Test Plan")

    base_dec = december_2026_closing(client, headers, plan["base_id"])
    test_plan_dec = december_2026_closing(client, headers, test_plan["id"])
    assert base_dec == test_plan_dec == 28_140_000


def test_m1_case_25_3_plan_with_an_item_added(client: TestClient) -> None:
    headers = register(client, "m1-25-3@example.com")
    setup_base_plan(client, headers)
    buy_house = create_plan(client, headers, "Buy House")
    resp = client.post(
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
    assert resp.status_code == 201

    body = forecast(client, headers, buy_house["id"], horizon=12)
    months = {m["month"]: m["closing_balance_minor"] for m in body["months"]}
    assert months["2026-05"] == 14_350_000  # 143,500 -- identical to Base through May
    assert months["2026-06"] == 15_670_000  # 156,700
    assert months["2026-12"] == 23_590_000  # 235,900


def test_m1_case_25_4_plan_with_an_item_removed(client: TestClient) -> None:
    headers = register(client, "m1-25-4@example.com")
    plan = setup_base_plan(client, headers)
    no_rent = create_plan(client, headers, "No Rent")
    resp = client.post(
        f"/v1/scenarios/{no_rent['id']}/overlays",
        headers=headers,
        json={"base_transaction_id": plan["rent_id"], "op": "exclude"},
    )
    assert resp.status_code == 201

    body = forecast(client, headers, no_rent["id"], horizon=12)
    months = {m["month"]: m["closing_balance_minor"] for m in body["months"]}
    assert months["2026-01"] == 6_920_000  # 69,200 -- absent from the very first month
    assert months["2026-12"] == 33_540_000  # 335,400


def test_m1_case_25_5_plan_with_an_item_changed_to_end_early(client: TestClient) -> None:
    headers = register(client, "m1-25-5@example.com")
    plan = setup_base_plan(client, headers)
    rent_ends = create_plan(client, headers, "Rent Ends")
    resp = client.post(
        f"/v1/scenarios/{rent_ends['id']}/overlays",
        headers=headers,
        json={
            "base_transaction_id": plan["rent_id"],
            "op": "override",
            "ovr_end_date": "2026-05-31",
        },
    )
    assert resp.status_code == 201

    body = forecast(client, headers, rent_ends["id"], horizon=12)
    months = {m["month"]: m["closing_balance_minor"] for m in body["months"]}
    assert months["2026-01"] == 6_470_000  # 64,700 -- same as Base before the end date
    assert months["2026-05"] == 14_350_000  # 143,500
    assert months["2026-06"] == 16_770_000  # 167,700
    assert months["2026-12"] == 31_290_000  # 312,900

    # Compare with 25.4: removing an item and changing it to end early
    # produce different results, and both are correct (R18).
    assert months["2026-12"] != 33_540_000


def _build_buy_house_25_6(client: TestClient, headers: dict, plan: dict) -> dict:
    """Base Plan with two changes: Rent ends 31-05-2026, Mortgage added
    from 01-06-2026 -- the "Buy House" referenced by cases 25.6-25.8,
    25.15 and 25.17."""
    buy_house = create_plan(client, headers, "Buy House")
    resp = client.post(
        f"/v1/scenarios/{buy_house['id']}/overlays",
        headers=headers,
        json={
            "base_transaction_id": plan["rent_id"],
            "op": "override",
            "ovr_end_date": "2026-05-31",
        },
    )
    assert resp.status_code == 201
    resp = client.post(
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
    assert resp.status_code == 201
    return buy_house


def test_m1_case_25_6_a_realistic_combined_plan(client: TestClient) -> None:
    headers = register(client, "m1-25-6@example.com")
    plan = setup_base_plan(client, headers)
    buy_house = _build_buy_house_25_6(client, headers, plan)

    body = forecast(client, headers, buy_house["id"], horizon=12)
    months = {m["month"]: m["closing_balance_minor"] for m in body["months"]}
    expected = {
        "2026-01": 6_470_000,
        "2026-02": 8_440_000,
        "2026-03": 10_410_000,
        "2026-04": 12_380_000,
        "2026-05": 14_350_000,
        "2026-06": 16_120_000,
        "2026-07": 17_890_000,
        "2026-08": 19_660_000,
        "2026-09": 21_430_000,
        "2026-10": 23_200_000,
        "2026-11": 24_970_000,
        "2026-12": 26_740_000,
    }
    for month, closing in expected.items():
        assert months[month] == closing, month


def test_m1_case_25_7_a_base_change_flows_into_every_plan(client: TestClient) -> None:
    headers = register(client, "m1-25-7@example.com")
    plan = setup_base_plan(client, headers)
    buy_house = _build_buy_house_25_6(client, headers, plan)

    resp = client.patch(
        f"/v1/transactions/{plan['salary_id']}", headers=headers, json={"amount_minor": 2_800_000}
    )
    assert resp.status_code == 200

    assert december_2026_closing(client, headers, plan["base_id"]) == 31_740_000  # 317,400
    assert december_2026_closing(client, headers, buy_house["id"]) == 30_340_000  # 303,400


def test_m1_case_25_8_plan_changes_never_affect_the_base_plan(client: TestClient) -> None:
    headers = register(client, "m1-25-8@example.com")
    plan = setup_base_plan(client, headers)
    _build_buy_house_25_6(client, headers, plan)

    assert december_2026_closing(client, headers, plan["base_id"]) == 28_140_000  # unchanged
    base_items = resolved_transactions(client, headers, plan["base_id"])
    assert by_name(base_items, "Rent")["end_date"] is None
    assert all(i["name"] != "Mortgage" for i in base_items)


def test_m1_case_25_9_plan_with_a_different_current_cash_balance(client: TestClient) -> None:
    headers = register(client, "m1-25-9@example.com")
    setup_base_plan(client, headers)
    windfall = create_plan(client, headers, "Windfall", current_balance_override_minor=34_500_000)

    body = forecast(client, headers, windfall["id"], horizon=12)
    for i, month in enumerate(body["months"], start=1):
        assert month["closing_balance_minor"] == base_plan_expected_months()[i - 1] + 30_000_000
    assert body["months"][-1]["closing_balance_minor"] == 58_140_000  # 581,400

    me = client.get("/v1/me", headers=headers).json()
    assert me["settings"]["current_balance_minor"] == 4_500_000  # Base's own balance untouched


def test_m1_case_25_10_base_item_changed_plan_had_inherited_it(client: TestClient) -> None:
    headers = register(client, "m1-25-10@example.com")
    plan = setup_base_plan(client, headers)
    test_plan = create_plan(client, headers, "Test Plan")

    resp = client.patch(
        f"/v1/transactions/{plan['utilities_id']}", headers=headers, json={"amount_minor": 100_000}
    )
    assert resp.status_code == 200

    assert december_2026_closing(client, headers, plan["base_id"]) == 27_900_000  # 279,000
    assert december_2026_closing(client, headers, test_plan["id"]) == 27_900_000


def test_m1_case_25_11_base_item_changed_in_a_field_the_plan_did_not_override(
    client: TestClient,
) -> None:
    """The single most important case in this section: "Rent Ends" must
    pick up the new rent amount for the months it doesn't override,
    while keeping its own end-date override. 310,400 -- not 312,900,
    which would mean the plan snapshotted the whole row instead of
    patching only the overridden field."""
    headers = register(client, "m1-25-11@example.com")
    plan = setup_base_plan(client, headers)
    rent_ends = create_plan(client, headers, "Rent Ends")
    resp = client.post(
        f"/v1/scenarios/{rent_ends['id']}/overlays",
        headers=headers,
        json={
            "base_transaction_id": plan["rent_id"],
            "op": "override",
            "ovr_end_date": "2026-05-31",
        },
    )
    assert resp.status_code == 201
    assert december_2026_closing(client, headers, rent_ends["id"]) == 31_290_000  # 312,900, sanity

    resp = client.patch(
        f"/v1/transactions/{plan['rent_id']}", headers=headers, json={"amount_minor": 500_000}
    )
    assert resp.status_code == 200

    assert december_2026_closing(client, headers, plan["base_id"]) == 27_540_000  # 275,400
    assert december_2026_closing(client, headers, rent_ends["id"]) == 31_040_000  # 310,400


def test_m1_case_25_12_base_item_deleted_plan_had_inherited_it(client: TestClient) -> None:
    headers = register(client, "m1-25-12@example.com")
    plan = setup_base_plan(client, headers)
    test_plan = create_plan(client, headers, "Test Plan")

    resp = client.delete(f"/v1/transactions/{plan['utilities_id']}", headers=headers)
    assert resp.status_code == 204

    assert december_2026_closing(client, headers, plan["base_id"]) == 29_100_000  # 291,000
    assert december_2026_closing(client, headers, test_plan["id"]) == 29_100_000
    for scenario_id in (plan["base_id"], test_plan["id"]):
        assert all(
            i["name"] != "Utilities" for i in resolved_transactions(client, headers, scenario_id)
        )


def test_m1_case_25_13_base_item_deleted_plan_had_changed_it(client: TestClient) -> None:
    headers = register(client, "m1-25-13@example.com")
    plan = setup_base_plan(client, headers)
    rent_ends = create_plan(client, headers, "Rent Ends")
    client.post(
        f"/v1/scenarios/{rent_ends['id']}/overlays",
        headers=headers,
        json={
            "base_transaction_id": plan["rent_id"],
            "op": "override",
            "ovr_end_date": "2026-05-31",
        },
    )

    dependents = client.get(
        f"/v1/transactions/{plan['rent_id']}/dependents", headers=headers
    ).json()
    assert dependents["count"] == 1
    assert dependents["scenarios"][0]["name"] == "Rent Ends"

    resp = client.delete(f"/v1/transactions/{plan['rent_id']}", headers=headers)
    assert resp.status_code == 204

    assert december_2026_closing(client, headers, plan["base_id"]) == 33_540_000  # 335,400
    assert december_2026_closing(client, headers, rent_ends["id"]) == 33_540_000
    for scenario_id in (plan["base_id"], rent_ends["id"]):
        assert all(i["name"] != "Rent" for i in resolved_transactions(client, headers, scenario_id))


def test_m1_case_25_14_base_item_deleted_plan_had_removed_it(client: TestClient) -> None:
    headers = register(client, "m1-25-14@example.com")
    plan = setup_base_plan(client, headers)
    no_rent = create_plan(client, headers, "No Rent")
    client.post(
        f"/v1/scenarios/{no_rent['id']}/overlays",
        headers=headers,
        json={"base_transaction_id": plan["rent_id"], "op": "exclude"},
    )
    assert december_2026_closing(client, headers, no_rent["id"]) == 33_540_000  # sanity, case 25.4

    resp = client.delete(f"/v1/transactions/{plan['rent_id']}", headers=headers)
    assert resp.status_code == 204

    assert december_2026_closing(client, headers, no_rent["id"]) == 33_540_000  # unchanged
    assert december_2026_closing(client, headers, plan["base_id"]) == 33_540_000


def test_m1_case_25_15_duplicate_preserves_inheritance_and_changes(client: TestClient) -> None:
    headers = register(client, "m1-25-15@example.com")
    plan = setup_base_plan(client, headers)
    buy_house = _build_buy_house_25_6(client, headers, plan)
    assert december_2026_closing(client, headers, buy_house["id"]) == 26_740_000  # sanity, 25.6

    # Step 1: duplicate.
    resp = client.post(
        f"/v1/scenarios/{buy_house['id']}/duplicate",
        headers=headers,
        json={"name": "Buy House (copy)"},
    )
    assert resp.status_code == 201
    copy = resp.json()
    copy_body = forecast(client, headers, copy["id"], horizon=12)
    buy_house_body = forecast(client, headers, buy_house["id"], horizon=12)
    assert copy_body["months"] == buy_house_body["months"]
    assert copy_body["months"][-1]["closing_balance_minor"] == 26_740_000

    # Step 2: inspect the copy's items.
    copy_items = resolved_transactions(client, headers, copy["id"])
    assert by_name(copy_items, "Salary")["origin"] == "inherited"
    assert by_name(copy_items, "Utilities")["origin"] == "inherited"
    rent = by_name(copy_items, "Rent")
    assert rent["origin"] == "overridden"
    assert rent["end_date"] == "2026-05-31"
    mortgage = by_name(copy_items, "Mortgage")
    assert mortgage["origin"] == "added"

    # Step 3: change Base salary -- the inheritance link survives duplication.
    client.patch(
        f"/v1/transactions/{plan['salary_id']}", headers=headers, json={"amount_minor": 2_800_000}
    )
    assert december_2026_closing(client, headers, plan["base_id"]) == 31_740_000  # 317,400
    assert december_2026_closing(client, headers, buy_house["id"]) == 30_340_000  # 303,400
    assert december_2026_closing(client, headers, copy["id"]) == 30_340_000  # 303,400

    # Step 4: change the copy's own mortgage only -- the two plans are
    # independent of each other.
    resp = client.patch(
        f"/v1/transactions/{mortgage['id']}", headers=headers, json={"amount_minor": 700_000}
    )
    assert resp.status_code == 200
    assert december_2026_closing(client, headers, copy["id"]) == 29_990_000  # 299,900
    assert december_2026_closing(client, headers, buy_house["id"]) == 30_340_000  # unaffected
    assert december_2026_closing(client, headers, plan["base_id"]) == 31_740_000  # unaffected


def test_m1_case_25_16_duplicating_the_base_plan(client: TestClient) -> None:
    headers = register(client, "m1-25-16@example.com")
    plan = setup_base_plan(client, headers)

    # Step 1: duplicate Base.
    resp = client.post(
        f"/v1/scenarios/{plan['base_id']}/duplicate", headers=headers, json={"name": "New Plan"}
    )
    assert resp.status_code == 201
    new_plan = resp.json()
    assert december_2026_closing(client, headers, new_plan["id"]) == 28_140_000  # 281,400

    # Step 2: each item appears exactly once -- the specific bug M1 case
    # 25.16 (and this project's own duplicate-doubles-Base-items defect,
    # found and fixed this session) exists to catch.
    items = resolved_transactions(client, headers, new_plan["id"])
    assert len(items) == 3
    assert {i["name"] for i in items} == {"Salary", "Rent", "Utilities"}
    assert all(i["origin"] == "inherited" for i in items)

    # Step 3: a Base change flows into the duplicate too.
    client.patch(
        f"/v1/transactions/{plan['utilities_id']}", headers=headers, json={"amount_minor": 100_000}
    )
    assert december_2026_closing(client, headers, plan["base_id"]) == 27_900_000  # 279,000
    assert december_2026_closing(client, headers, new_plan["id"]) == 27_900_000


def test_m1_case_25_17_archive_and_restore_with_a_base_change_in_between(
    client: TestClient,
) -> None:
    headers = register(client, "m1-25-17@example.com")
    plan = setup_base_plan(client, headers)
    buy_house = _build_buy_house_25_6(client, headers, plan)

    # Step 1: archive.
    resp = client.post(f"/v1/scenarios/{buy_house['id']}/archive", headers=headers)
    assert resp.status_code == 200
    active_ids = {s["id"] for s in client.get("/v1/scenarios", headers=headers).json()["items"]}
    assert buy_house["id"] not in active_ids
    all_ids = {
        s["id"]
        for s in client.get(
            "/v1/scenarios", headers=headers, params={"include_archived": "true"}
        ).json()["items"]
    }
    assert buy_house["id"] in all_ids

    # Step 2: change Base salary while archived.
    client.patch(
        f"/v1/transactions/{plan['salary_id']}", headers=headers, json={"amount_minor": 2_800_000}
    )
    assert december_2026_closing(client, headers, plan["base_id"]) == 31_740_000  # 317,400

    # Step 3: restore -- its own changes are intact.
    resp = client.post(f"/v1/scenarios/{buy_house['id']}/unarchive", headers=headers)
    assert resp.status_code == 200
    active_ids = {s["id"] for s in client.get("/v1/scenarios", headers=headers).json()["items"]}
    assert buy_house["id"] in active_ids
    items = resolved_transactions(client, headers, buy_house["id"])
    assert by_name(items, "Rent")["end_date"] == "2026-05-31"
    assert by_name(items, "Mortgage")["origin"] == "added"

    # Step 4: the restored plan reflects the new Base salary.
    assert december_2026_closing(client, headers, buy_house["id"]) == 30_340_000  # 303,400
