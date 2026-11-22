"""Transaction CRUD: validation rules, direction immutability, the
per-scenario cap, and cross-user/cross-scenario ownership."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _auth_headers(client: TestClient, email: str = "txn@example.com") -> dict[str, str]:
    resp = client.post(
        "/v1/auth/register", json={"email": email, "password": "correct-horse", "name": "Test User"}
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _base_scenario_id(client: TestClient, headers: dict) -> str:
    return client.get("/v1/scenarios", headers=headers).json()["items"][0]["id"]


def _create_txn(client: TestClient, headers: dict, scenario_id: str, **overrides) -> dict:
    body = {
        "name": "Rent",
        "amount_minor": 300000,
        "direction": "expense",
        "recurrence": "monthly",
        "start_date": "2026-01-01",
        **overrides,
    }
    return client.post(
        f"/v1/scenarios/{scenario_id}/transactions", headers=headers, json=body
    ).json()


def test_create_and_list_transaction(client: TestClient) -> None:
    headers = _auth_headers(client)
    scenario_id = _base_scenario_id(client, headers)

    created = client.post(
        f"/v1/scenarios/{scenario_id}/transactions",
        headers=headers,
        json={
            "name": "Rent",
            "amount_minor": 300000,
            "direction": "expense",
            "recurrence": "monthly",
            "start_date": "2026-01-01",
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "Rent"
    assert body["origin"] == "own"  # Base's own transaction
    assert body["overlay_id"] is None  # no overlay -- this row isn't one

    listed = client.get(f"/v1/scenarios/{scenario_id}/transactions", headers=headers).json()[
        "items"
    ]
    assert len(listed) == 1
    assert listed[0]["id"] == body["id"]


def test_added_transaction_in_non_base_scenario_has_added_origin(client: TestClient) -> None:
    headers = _auth_headers(client)
    plan = client.post("/v1/scenarios", headers=headers, json={"name": ["Buy House"]}).json()[
        "items"
    ][0]
    created = _create_txn(client, headers, plan["id"], name="Mortgage")
    assert created["origin"] == "added"
    assert created["overlay_id"] is None  # no overlay -- this row isn't one


def test_amount_not_positive_is_rejected(client: TestClient) -> None:
    headers = _auth_headers(client)
    scenario_id = _base_scenario_id(client, headers)
    resp = client.post(
        f"/v1/scenarios/{scenario_id}/transactions",
        headers=headers,
        json={
            "name": "Bad",
            "amount_minor": 0,
            "direction": "expense",
            "recurrence": "monthly",
            "start_date": "2026-01-01",
        },
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "transaction.amount_not_positive"


def test_end_before_start_is_rejected(client: TestClient) -> None:
    headers = _auth_headers(client)
    scenario_id = _base_scenario_id(client, headers)
    resp = client.post(
        f"/v1/scenarios/{scenario_id}/transactions",
        headers=headers,
        json={
            "name": "Bad dates",
            "amount_minor": 1000,
            "direction": "expense",
            "recurrence": "monthly",
            "start_date": "2026-06-01",
            "end_date": "2026-01-01",
        },
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "transaction.end_before_start"


def test_one_time_with_end_date_is_rejected(client: TestClient) -> None:
    headers = _auth_headers(client)
    scenario_id = _base_scenario_id(client, headers)
    resp = client.post(
        f"/v1/scenarios/{scenario_id}/transactions",
        headers=headers,
        json={
            "name": "Bonus",
            "amount_minor": 1000,
            "direction": "income",
            "recurrence": "one_time",
            "start_date": "2026-01-01",
            "end_date": "2026-02-01",
        },
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "transaction.one_time_has_end_date"


def test_unknown_category_id_is_rejected(client: TestClient) -> None:
    headers = _auth_headers(client)
    scenario_id = _base_scenario_id(client, headers)
    resp = client.post(
        f"/v1/scenarios/{scenario_id}/transactions",
        headers=headers,
        json={
            "name": "Rent",
            "amount_minor": 1000,
            "direction": "expense",
            "recurrence": "monthly",
            "start_date": "2026-01-01",
            "category_id": "00000000-0000-0000-0000-000000000000",
        },
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation.invalid"


def test_create_with_system_category_succeeds(client: TestClient) -> None:
    headers = _auth_headers(client)
    scenario_id = _base_scenario_id(client, headers)
    categories = client.get("/v1/categories", headers=headers).json()["items"]
    housing_category = next(c for c in categories if c["key"] == "housing")

    resp = client.post(
        f"/v1/scenarios/{scenario_id}/transactions",
        headers=headers,
        json={
            "name": "Rent",
            "amount_minor": 1000,
            "direction": "expense",
            "recurrence": "monthly",
            "start_date": "2026-01-01",
            "category_id": housing_category["id"],
        },
    )
    assert resp.status_code == 201
    assert resp.json()["category_id"] == housing_category["id"]


def test_direction_is_immutable(client: TestClient) -> None:
    headers = _auth_headers(client)
    scenario_id = _base_scenario_id(client, headers)
    txn = _create_txn(client, headers, scenario_id)

    resp = client.patch(
        f"/v1/transactions/{txn['id']}", headers=headers, json={"direction": "income"}
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "transaction.direction_immutable"


def test_patch_updates_fields_and_preserves_others(client: TestClient) -> None:
    headers = _auth_headers(client)
    scenario_id = _base_scenario_id(client, headers)
    txn = _create_txn(client, headers, scenario_id, amount_minor=100000)

    resp = client.patch(
        f"/v1/transactions/{txn['id']}", headers=headers, json={"amount_minor": 150000}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["amount_minor"] == 150000
    assert body["name"] == "Rent"  # untouched


def test_patch_unset_end_date_makes_it_open_ended(client: TestClient) -> None:
    headers = _auth_headers(client)
    scenario_id = _base_scenario_id(client, headers)
    txn = _create_txn(client, headers, scenario_id, end_date="2026-12-01")
    assert txn["end_date"] == "2026-12-01"

    resp = client.patch(
        f"/v1/transactions/{txn['id']}", headers=headers, json={"unset_end_date": True}
    )
    assert resp.status_code == 200
    assert resp.json()["end_date"] is None


def test_patch_changing_recurrence_to_one_time_with_existing_end_date_is_rejected(
    client: TestClient,
) -> None:
    headers = _auth_headers(client)
    scenario_id = _base_scenario_id(client, headers)
    txn = _create_txn(client, headers, scenario_id, end_date="2026-12-01")

    resp = client.patch(
        f"/v1/transactions/{txn['id']}", headers=headers, json={"recurrence": "one_time"}
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "transaction.one_time_has_end_date"


def test_delete_transaction(client: TestClient) -> None:
    headers = _auth_headers(client)
    scenario_id = _base_scenario_id(client, headers)
    txn = _create_txn(client, headers, scenario_id)

    resp = client.delete(f"/v1/transactions/{txn['id']}", headers=headers)
    assert resp.status_code == 200

    listed = client.get(f"/v1/scenarios/{scenario_id}/transactions", headers=headers).json()[
        "items"
    ]
    assert listed == []


def test_no_limit_on_number_of_transactions_per_scenario(client: TestClient) -> None:
    """Explicit product decision: no cap on how many transactions a plan
    can hold (supersedes the earlier 500-per-scenario cap). Creating well
    past a plausible old threshold must keep working."""
    headers = _auth_headers(client)
    scenario_id = _base_scenario_id(client, headers)
    for i in range(20):
        resp = client.post(
            f"/v1/scenarios/{scenario_id}/transactions",
            headers=headers,
            json={
                "name": f"Txn {i}",
                "amount_minor": 1000,
                "direction": "expense",
                "recurrence": "monthly",
                "start_date": "2026-01-01",
            },
        )
        assert resp.status_code == 201


def test_transaction_not_found_for_another_user_returns_404(client: TestClient) -> None:
    headers_a = _auth_headers(client, email="owner2@example.com")
    headers_b = _auth_headers(client, email="intruder2@example.com")
    scenario_id = _base_scenario_id(client, headers_a)
    txn = _create_txn(client, headers_a, scenario_id)

    resp = client.patch(
        f"/v1/transactions/{txn['id']}", headers=headers_b, json={"amount_minor": 999}
    )
    assert resp.status_code == 404

    resp = client.delete(f"/v1/transactions/{txn['id']}", headers=headers_b)
    assert resp.status_code == 404


def test_cannot_list_transactions_of_another_users_scenario(client: TestClient) -> None:
    headers_a = _auth_headers(client, email="owner3@example.com")
    headers_b = _auth_headers(client, email="intruder3@example.com")
    scenario_id = _base_scenario_id(client, headers_a)

    resp = client.get(f"/v1/scenarios/{scenario_id}/transactions", headers=headers_b)
    assert resp.status_code == 404


def test_dependents_is_empty_for_a_transaction_with_no_overlays(client: TestClient) -> None:
    headers = _auth_headers(client, email="nodeps@example.com")
    scenario_id = _base_scenario_id(client, headers)
    txn = _create_txn(client, headers, scenario_id)

    resp = client.get(f"/v1/transactions/{txn['id']}/dependents", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == {"count": 0, "scenarios": []}


def test_dependents_is_empty_for_a_scenario_local_transaction(client: TestClient) -> None:
    """A transaction created directly on a non-Base scenario can never be
    an overlay target -- overlays only ever target Base rows -- so this
    is a plain empty result, not an error."""
    headers = _auth_headers(client, email="localdeps@example.com")
    plan = client.post("/v1/scenarios", headers=headers, json={"name": ["Buy House"]}).json()[
        "items"
    ][0]
    txn = _create_txn(client, headers, plan["id"], name="Mortgage")

    resp = client.get(f"/v1/transactions/{txn['id']}/dependents", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == {"count": 0, "scenarios": []}


def test_dependents_lists_every_scenario_holding_an_overlay(client: TestClient) -> None:
    headers = _auth_headers(client, email="deps@example.com")
    base_id = _base_scenario_id(client, headers)
    rent = _create_txn(client, headers, base_id)

    plan_a = client.post("/v1/scenarios", headers=headers, json={"name": ["Buy House"]}).json()[
        "items"
    ][0]
    plan_b = client.post("/v1/scenarios", headers=headers, json={"name": ["Retire Early"]}).json()[
        "items"
    ][0]
    client.post(
        f"/v1/scenarios/{plan_a['id']}/overlays",
        headers=headers,
        json={"base_transaction_id": rent["id"], "op": "exclude"},
    )
    client.post(
        f"/v1/scenarios/{plan_b['id']}/overlays",
        headers=headers,
        json={"base_transaction_id": rent["id"], "op": "override", "ovr_amount_minor": 350000},
    )
    # A third plan with no overlay on this transaction -- must not appear.
    client.post("/v1/scenarios", headers=headers, json={"name": ["Untouched"]})

    resp = client.get(f"/v1/transactions/{rent['id']}/dependents", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 2
    names = {s["name"] for s in body["scenarios"]}
    assert names == {"Buy House", "Retire Early"}


def test_dependents_not_found_for_another_users_transaction(client: TestClient) -> None:
    headers_a = _auth_headers(client, email="depsowner@example.com")
    headers_b = _auth_headers(client, email="depsintruder@example.com")
    scenario_id = _base_scenario_id(client, headers_a)
    txn = _create_txn(client, headers_a, scenario_id)

    resp = client.get(f"/v1/transactions/{txn['id']}/dependents", headers=headers_b)
    assert resp.status_code == 404


def test_dependents_requires_auth(client: TestClient) -> None:
    resp = client.get("/v1/transactions/00000000-0000-0000-0000-000000000000/dependents")
    assert resp.status_code == 401


# ---- UAT-008 Part A: transaction date bounds and date behaviour -------------


def _post_txn(client: TestClient, headers: dict, scenario_id: str, **overrides):
    body = {
        "name": "Dated",
        "amount_minor": 1000,
        "direction": "expense",
        "recurrence": "monthly",
        "start_date": "2026-01-01",
        **overrides,
    }
    return client.post(f"/v1/scenarios/{scenario_id}/transactions", headers=headers, json=body)


def test_start_date_outside_bounds_is_rejected_on_create(client: TestClient) -> None:
    headers = _auth_headers(client, email="bounds1@example.com")
    sid = _base_scenario_id(client, headers)

    for bad in ("1999-12-31", "2101-01-01", "0001-01-01", "9999-12-31"):
        resp = _post_txn(client, headers, sid, start_date=bad)
        assert resp.status_code == 422, bad
        err = resp.json()["error"]
        assert err["code"] == "validation.invalid"
        assert err["params"]["field"] == "start_date"


def test_dates_exactly_on_the_bounds_are_accepted(client: TestClient) -> None:
    headers = _auth_headers(client, email="bounds2@example.com")
    sid = _base_scenario_id(client, headers)

    assert _post_txn(client, headers, sid, start_date="2000-01-01").status_code == 201
    assert (
        _post_txn(
            client, headers, sid, name="Late", start_date="2100-01-01", end_date="2100-12-31"
        ).status_code
        == 201
    )


def test_end_date_outside_bounds_is_rejected(client: TestClient) -> None:
    headers = _auth_headers(client, email="bounds3@example.com")
    sid = _base_scenario_id(client, headers)

    resp = _post_txn(client, headers, sid, end_date="2101-01-01")
    assert resp.status_code == 422
    assert resp.json()["error"]["params"]["field"] == "end_date"


def test_patch_dates_outside_bounds_are_rejected(client: TestClient) -> None:
    headers = _auth_headers(client, email="bounds4@example.com")
    sid = _base_scenario_id(client, headers)
    txn = _create_txn(client, headers, sid)

    for field, bad in (("start_date", "1990-05-05"), ("end_date", "2200-01-01")):
        resp = client.patch(f"/v1/transactions/{txn['id']}", headers=headers, json={field: bad})
        assert resp.status_code == 422, field
        assert resp.json()["error"]["params"]["field"] == field

    ok = client.patch(
        f"/v1/transactions/{txn['id']}", headers=headers, json={"start_date": "2026-02-15"}
    )
    assert ok.status_code == 200
    assert ok.json()["start_date"] == "2026-02-15"


def test_overlay_dates_outside_bounds_are_rejected(client: TestClient) -> None:
    headers = _auth_headers(client, email="bounds5@example.com")
    base_id = _base_scenario_id(client, headers)
    txn = _create_txn(client, headers, base_id)
    plan = client.post("/v1/scenarios", headers=headers, json={"name": ["Plan B"]}).json()["items"][
        0
    ]

    resp = client.post(
        f"/v1/scenarios/{plan['id']}/overlays",
        headers=headers,
        json={"base_transaction_id": txn["id"], "op": "override", "ovr_start_date": "1900-01-01"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["params"]["field"] == "ovr_start_date"


def test_one_time_item_only_produces_an_occurrence_on_its_own_date(client: TestClient) -> None:
    headers = _auth_headers(client, email="dates1@example.com")
    sid = _base_scenario_id(client, headers)
    _post_txn(client, headers, sid, name="Bonus", recurrence="one_time", start_date="2026-03-15")

    resp = client.get(
        f"/v1/scenarios/{sid}/forecast",
        headers=headers,
        params={"horizon": 5, "anchor": "2026-01", "include_occurrences": True},
    )
    assert resp.status_code == 200
    bonus = [o for o in resp.json()["occurrences"] if o["name"] == "Bonus"]
    assert [o["on"] for o in bonus] == ["2026-03-15"]


def test_recurring_item_uses_its_start_date_day_in_every_month(client: TestClient) -> None:
    headers = _auth_headers(client, email="dates2@example.com")
    sid = _base_scenario_id(client, headers)
    _post_txn(client, headers, sid, name="Salary", start_date="2026-01-22")

    resp = client.get(
        f"/v1/scenarios/{sid}/forecast",
        headers=headers,
        params={"horizon": 4, "anchor": "2026-01", "include_occurrences": True},
    )
    dates = [o["on"] for o in resp.json()["occurrences"] if o["name"] == "Salary"]
    assert dates == ["2026-01-22", "2026-02-22", "2026-03-22", "2026-04-22"]


def test_item_dated_before_the_anchor_month_does_not_affect_the_forecast(
    client: TestClient,
) -> None:
    headers = _auth_headers(client, email="dates3@example.com")
    sid = _base_scenario_id(client, headers)
    _post_txn(
        client,
        headers,
        sid,
        name="Old",
        recurrence="one_time",
        start_date="2025-06-10",
    )

    resp = client.get(
        f"/v1/scenarios/{sid}/forecast",
        headers=headers,
        params={"horizon": 3, "anchor": "2026-01", "include_occurrences": True},
    )
    assert resp.status_code == 200
    assert [o for o in resp.json()["occurrences"] if o["name"] == "Old"] == []
