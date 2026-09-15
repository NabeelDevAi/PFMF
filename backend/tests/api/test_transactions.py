"""Transaction CRUD: validation rules, direction immutability, the
per-scenario cap, and cross-user/cross-scenario ownership."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _auth_headers(client: TestClient, email: str = "txn@example.com") -> dict[str, str]:
    resp = client.post("/v1/auth/register", json={"email": email, "password": "correct-horse"})
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

    listed = client.get(f"/v1/scenarios/{scenario_id}/transactions", headers=headers).json()[
        "items"
    ]
    assert len(listed) == 1
    assert listed[0]["id"] == body["id"]


def test_added_transaction_in_non_base_scenario_has_added_origin(client: TestClient) -> None:
    headers = _auth_headers(client)
    plan = client.post("/v1/scenarios", headers=headers, json={"name": "Buy House"}).json()
    created = _create_txn(client, headers, plan["id"], name="Mortgage")
    assert created["origin"] == "added"


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
    rent_category = next(c for c in categories if c["key"] == "rent")

    resp = client.post(
        f"/v1/scenarios/{scenario_id}/transactions",
        headers=headers,
        json={
            "name": "Rent",
            "amount_minor": 1000,
            "direction": "expense",
            "recurrence": "monthly",
            "start_date": "2026-01-01",
            "category_id": rent_category["id"],
        },
    )
    assert resp.status_code == 201
    assert resp.json()["category_id"] == rent_category["id"]


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
    assert resp.status_code == 204

    listed = client.get(f"/v1/scenarios/{scenario_id}/transactions", headers=headers).json()[
        "items"
    ]
    assert listed == []


def test_transaction_limit_reached(client: TestClient, monkeypatch) -> None:
    # Patch the name where transaction_service.py actually uses it, rather
    # than the Settings class itself -- reassigning a field on a cached
    # pydantic-settings instance isn't a supported/reliable operation.
    import app.services.transaction_service as transaction_service_module

    real_settings = transaction_service_module.get_settings()
    patched = real_settings.model_copy(update={"max_transactions_per_scenario": 2})
    monkeypatch.setattr(transaction_service_module, "get_settings", lambda: patched)

    headers = _auth_headers(client)
    scenario_id = _base_scenario_id(client, headers)
    _create_txn(client, headers, scenario_id, name="One")
    _create_txn(client, headers, scenario_id, name="Two")

    resp = client.post(
        f"/v1/scenarios/{scenario_id}/transactions",
        headers=headers,
        json={
            "name": "Three",
            "amount_minor": 1000,
            "direction": "expense",
            "recurrence": "monthly",
            "start_date": "2026-01-01",
        },
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "transaction.limit_reached"


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
    plan = client.post("/v1/scenarios", headers=headers, json={"name": "Buy House"}).json()
    txn = _create_txn(client, headers, plan["id"], name="Mortgage")

    resp = client.get(f"/v1/transactions/{txn['id']}/dependents", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == {"count": 0, "scenarios": []}


def test_dependents_lists_every_scenario_holding_an_overlay(client: TestClient) -> None:
    headers = _auth_headers(client, email="deps@example.com")
    base_id = _base_scenario_id(client, headers)
    rent = _create_txn(client, headers, base_id)

    plan_a = client.post("/v1/scenarios", headers=headers, json={"name": "Buy House"}).json()
    plan_b = client.post("/v1/scenarios", headers=headers, json={"name": "Retire Early"}).json()
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
    client.post("/v1/scenarios", headers=headers, json={"name": "Untouched"})

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
