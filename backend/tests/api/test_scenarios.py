"""Scenario CRUD, Base protection, duplicate, archive/unarchive, and
cross-user ownership (backend-plan/11's M3 done-criteria)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _auth_headers(client: TestClient, email: str = "scen@example.com") -> dict[str, str]:
    resp = client.post(
        "/v1/auth/register", json={"email": email, "password": "correct-horse", "name": "Test User"}
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _list_scenarios(client: TestClient, headers: dict) -> list[dict]:
    return client.get("/v1/scenarios", headers=headers).json()["items"]


def test_register_creates_exactly_one_base_scenario(client: TestClient) -> None:
    headers = _auth_headers(client)
    scenarios = _list_scenarios(client, headers)
    assert len(scenarios) == 1
    assert scenarios[0]["is_base"] is True
    assert scenarios[0]["name"] == "Base Plan"


def test_create_scenario(client: TestClient) -> None:
    headers = _auth_headers(client)
    resp = client.post("/v1/scenarios", headers=headers, json={"name": "Buy House"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Buy House"
    assert body["is_base"] is False
    assert body["current_balance_override_minor"] is None


def test_create_scenario_rejects_a_blank_name(client: TestClient) -> None:
    headers = _auth_headers(client)
    resp = client.post("/v1/scenarios", headers=headers, json={"name": ""})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation.invalid"


def test_create_scenario_rejects_a_whitespace_only_name(client: TestClient) -> None:
    headers = _auth_headers(client)
    resp = client.post("/v1/scenarios", headers=headers, json={"name": "   "})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation.invalid"


def test_create_scenario_duplicate_name_is_conflict(client: TestClient) -> None:
    headers = _auth_headers(client)
    client.post("/v1/scenarios", headers=headers, json={"name": "Buy House"})
    resp = client.post("/v1/scenarios", headers=headers, json={"name": "Buy House"})
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "scenario.name_taken"


def test_create_scenario_can_reuse_base_plan_name_for_a_different_user(client: TestClient) -> None:
    """Uniqueness is per-user, not global."""
    headers_a = _auth_headers(client, email="a@example.com")
    headers_b = _auth_headers(client, email="b@example.com")
    # Both users already have a scenario named "Base Plan" from registration
    # -- confirms the unique constraint is (user_id, name), not just (name).
    assert _list_scenarios(client, headers_a)[0]["name"] == "Base Plan"
    assert _list_scenarios(client, headers_b)[0]["name"] == "Base Plan"


def test_base_scenario_cannot_be_deleted(client: TestClient) -> None:
    headers = _auth_headers(client)
    base_id = _list_scenarios(client, headers)[0]["id"]
    resp = client.delete(f"/v1/scenarios/{base_id}", headers=headers)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "scenario.base_immutable"


def test_base_scenario_cannot_be_archived(client: TestClient) -> None:
    headers = _auth_headers(client)
    base_id = _list_scenarios(client, headers)[0]["id"]
    resp = client.post(f"/v1/scenarios/{base_id}/archive", headers=headers)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "scenario.base_immutable"


def test_non_base_scenario_can_be_deleted(client: TestClient) -> None:
    headers = _auth_headers(client)
    created = client.post("/v1/scenarios", headers=headers, json={"name": "Temp"}).json()
    resp = client.delete(f"/v1/scenarios/{created['id']}", headers=headers)
    assert resp.status_code == 200
    assert client.get(f"/v1/scenarios/{created['id']}", headers=headers).status_code == 404


def test_archive_and_unarchive_round_trip(client: TestClient) -> None:
    headers = _auth_headers(client)
    created = client.post("/v1/scenarios", headers=headers, json={"name": "Someday"}).json()

    archived = client.post(f"/v1/scenarios/{created['id']}/archive", headers=headers)
    assert archived.status_code == 200
    assert archived.json()["archived_at"] is not None

    # Archived scenarios are excluded from the default list.
    assert created["id"] not in {s["id"] for s in _list_scenarios(client, headers)}
    all_scenarios = client.get("/v1/scenarios?include_archived=true", headers=headers).json()[
        "items"
    ]
    assert created["id"] in {s["id"] for s in all_scenarios}

    unarchived = client.post(f"/v1/scenarios/{created['id']}/unarchive", headers=headers)
    assert unarchived.status_code == 200
    assert unarchived.json()["archived_at"] is None
    assert created["id"] in {s["id"] for s in _list_scenarios(client, headers)}


def test_unarchive_a_scenario_that_is_not_archived_is_rejected(client: TestClient) -> None:
    headers = _auth_headers(client)
    created = client.post("/v1/scenarios", headers=headers, json={"name": "Never archived"}).json()

    resp = client.post(f"/v1/scenarios/{created['id']}/unarchive", headers=headers)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "scenario.not_archived"


def test_archived_scenario_is_rejected_as_a_duplicate_source(client: TestClient) -> None:
    """Architecture §6.2: rejected as a duplicate source -- restore first
    (screen-flow §8.1)."""
    headers = _auth_headers(client)
    created = client.post("/v1/scenarios", headers=headers, json={"name": "Someday"}).json()
    client.post(f"/v1/scenarios/{created['id']}/archive", headers=headers)

    resp = client.post(f"/v1/scenarios/{created['id']}/duplicate", headers=headers, json={})
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "scenario.archived"


def test_archived_scenario_is_rejected_as_a_compare_operand(client: TestClient) -> None:
    """Architecture §6.2: rejected as a comparison operand."""
    headers = _auth_headers(client)
    base_id = _list_scenarios(client, headers)[0]["id"]
    created = client.post("/v1/scenarios", headers=headers, json={"name": "Someday"}).json()
    client.post(f"/v1/scenarios/{created['id']}/archive", headers=headers)

    resp = client.get(
        "/v1/forecast/compare",
        headers=headers,
        params={"a": base_id, "b": created["id"], "horizon": 12},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "scenario.archived"

    # Order doesn't matter -- an archived A is rejected too.
    resp = client.get(
        "/v1/forecast/compare",
        headers=headers,
        params={"a": created["id"], "b": base_id, "horizon": 12},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "scenario.archived"


def test_patch_scenario_rename_and_current_balance_override(client: TestClient) -> None:
    headers = _auth_headers(client)
    created = client.post("/v1/scenarios", headers=headers, json={"name": "Draft"}).json()

    resp = client.patch(
        f"/v1/scenarios/{created['id']}",
        headers=headers,
        json={"name": "Buy House", "current_balance_override_minor": 250000},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Buy House"
    assert resp.json()["current_balance_override_minor"] == 250000


def test_patch_scenario_unset_current_balance_override(client: TestClient) -> None:
    headers = _auth_headers(client)
    created = client.post(
        "/v1/scenarios",
        headers=headers,
        json={"name": "Draft", "current_balance_override_minor": 100},
    ).json()

    resp = client.patch(
        f"/v1/scenarios/{created['id']}",
        headers=headers,
        json={"unset_current_balance_override": True},
    )
    assert resp.status_code == 200
    assert resp.json()["current_balance_override_minor"] is None


def test_patch_scenario_rejects_a_blank_name(client: TestClient) -> None:
    headers = _auth_headers(client)
    created = client.post("/v1/scenarios", headers=headers, json={"name": "Draft"}).json()

    resp = client.patch(f"/v1/scenarios/{created['id']}", headers=headers, json={"name": "   "})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation.invalid"


def test_duplicate_scenario_rejects_a_blank_name(client: TestClient) -> None:
    headers = _auth_headers(client)
    source = client.post("/v1/scenarios", headers=headers, json={"name": "Source"}).json()

    resp = client.post(
        f"/v1/scenarios/{source['id']}/duplicate", headers=headers, json={"name": "  "}
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation.invalid"


def test_duplicate_scenario_copies_own_transactions_with_a_new_id(client: TestClient) -> None:
    headers = _auth_headers(client)
    source = client.post("/v1/scenarios", headers=headers, json={"name": "Source"}).json()
    client.post(
        f"/v1/scenarios/{source['id']}/transactions",
        headers=headers,
        json={
            "name": "Rent",
            "amount_minor": 300000,
            "direction": "expense",
            "recurrence": "monthly",
            "start_date": "2026-01-01",
        },
    )

    resp = client.post(f"/v1/scenarios/{source['id']}/duplicate", headers=headers, json={})
    assert resp.status_code == 201
    copy = resp.json()
    assert copy["id"] != source["id"]
    assert copy["name"] == "Source (copy)"
    assert copy["is_base"] is False

    copied_txns = client.get(f"/v1/scenarios/{copy['id']}/transactions", headers=headers).json()[
        "items"
    ]
    assert len(copied_txns) == 1
    assert copied_txns[0]["name"] == "Rent"
    assert copied_txns[0]["scenario_id"] == copy["id"]

    # The original is untouched.
    source_txns = client.get(f"/v1/scenarios/{source['id']}/transactions", headers=headers).json()[
        "items"
    ]
    assert len(source_txns) == 1


def test_duplicating_base_produces_a_non_base_copy(client: TestClient) -> None:
    headers = _auth_headers(client)
    base_id = _list_scenarios(client, headers)[0]["id"]
    resp = client.post(
        f"/v1/scenarios/{base_id}/duplicate", headers=headers, json={"name": "Base copy"}
    )
    assert resp.status_code == 201
    assert resp.json()["is_base"] is False


def test_duplicate_of_base_with_transactions_yields_each_item_once(client: TestClient) -> None:
    """M1 case 25.16, the specific bug this guards: a naive duplicate
    copies Base's own rows into the copy *in addition to* the copy
    inheriting them normally, doubling every item. Base has nothing of
    its own to copy -- inheritance alone must reproduce it."""
    headers = _auth_headers(client)
    base_id = _list_scenarios(client, headers)[0]["id"]
    client.post(
        f"/v1/scenarios/{base_id}/transactions",
        headers=headers,
        json={
            "name": "Rent",
            "amount_minor": 300000,
            "direction": "expense",
            "recurrence": "monthly",
            "start_date": "2026-01-01",
        },
    )

    copy = client.post(
        f"/v1/scenarios/{base_id}/duplicate", headers=headers, json={"name": "Base copy"}
    ).json()

    resolved = client.get(f"/v1/scenarios/{copy['id']}/transactions", headers=headers).json()[
        "items"
    ]
    assert len(resolved) == 1
    assert resolved[0]["origin"] == "inherited"
    assert resolved[0]["name"] == "Rent"


def test_duplicate_of_derived_scenario_copies_its_overlays(client: TestClient) -> None:
    """D-13, M1 case 25.15: the copy must show the same excluded/
    overridden state as its source, not a plain inherited view."""
    headers = _auth_headers(client)
    base_id = _list_scenarios(client, headers)[0]["id"]
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
    source = client.post("/v1/scenarios", headers=headers, json={"name": "Buy House"}).json()
    client.post(
        f"/v1/scenarios/{source['id']}/overlays",
        headers=headers,
        json={"base_transaction_id": rent["id"], "op": "override", "ovr_amount_minor": 350000},
    )

    copy = client.post(f"/v1/scenarios/{source['id']}/duplicate", headers=headers, json={}).json()

    resolved = client.get(f"/v1/scenarios/{copy['id']}/transactions", headers=headers).json()[
        "items"
    ]
    assert len(resolved) == 1
    assert resolved[0]["origin"] == "overridden"
    assert resolved[0]["amount_minor"] == 350000


def test_duplicate_is_independent_of_its_source(client: TestClient) -> None:
    """M1 case 25.15 step 4: the copy gets its own overlay row, not a
    shared reference -- editing the source's overlay afterward must
    never touch the copy."""
    headers = _auth_headers(client)
    base_id = _list_scenarios(client, headers)[0]["id"]
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
    source = client.post("/v1/scenarios", headers=headers, json={"name": "Buy House"}).json()
    overlay = client.post(
        f"/v1/scenarios/{source['id']}/overlays",
        headers=headers,
        json={"base_transaction_id": rent["id"], "op": "override", "ovr_amount_minor": 350000},
    ).json()
    copy = client.post(f"/v1/scenarios/{source['id']}/duplicate", headers=headers, json={}).json()

    client.patch(
        f"/v1/scenarios/{source['id']}/overlays/{overlay['id']}",
        headers=headers,
        json={"ovr_amount_minor": 999999},
    )

    source_items = client.get(f"/v1/scenarios/{source['id']}/transactions", headers=headers).json()[
        "items"
    ]
    copy_items = client.get(f"/v1/scenarios/{copy['id']}/transactions", headers=headers).json()[
        "items"
    ]
    assert source_items[0]["amount_minor"] == 999999
    assert copy_items[0]["amount_minor"] == 350000  # untouched by editing the source's overlay


def test_duplicate_keeps_live_base_inheritance(client: TestClient) -> None:
    """M1 case 25.15: the copy keeps an independent live link to Base --
    a later Base change to a field neither the source nor the copy
    overrode must show up in both."""
    headers = _auth_headers(client)
    base_id = _list_scenarios(client, headers)[0]["id"]
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
    source = client.post("/v1/scenarios", headers=headers, json={"name": "Buy House"}).json()
    client.post(
        f"/v1/scenarios/{source['id']}/overlays",
        headers=headers,
        json={"base_transaction_id": rent["id"], "op": "override", "ovr_end_date": "2026-12-01"},
    )
    copy = client.post(f"/v1/scenarios/{source['id']}/duplicate", headers=headers, json={}).json()

    client.patch(f"/v1/transactions/{rent['id']}", headers=headers, json={"amount_minor": 400000})

    for scenario_id in (source["id"], copy["id"]):
        items = client.get(f"/v1/scenarios/{scenario_id}/transactions", headers=headers).json()[
            "items"
        ]
        assert items[0]["amount_minor"] == 400000  # picked up from Base, neither overrode it
        assert items[0]["end_date"] == "2026-12-01"  # each keeps its own override


def test_scenario_not_found_for_another_user_returns_404_not_403(client: TestClient) -> None:
    headers_a = _auth_headers(client, email="owner@example.com")
    headers_b = _auth_headers(client, email="intruder@example.com")
    scenario = client.post("/v1/scenarios", headers=headers_a, json={"name": "Private Plan"}).json()

    resp = client.get(f"/v1/scenarios/{scenario['id']}", headers=headers_b)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "resource.not_found"

    resp = client.delete(f"/v1/scenarios/{scenario['id']}", headers=headers_b)
    assert resp.status_code == 404


def test_no_limit_on_number_of_scenarios(client: TestClient) -> None:
    """Explicit product decision: no cap on how many plans an account can
    hold (supersedes the earlier 50-plan cap and its archived-scenario
    carve-out). Creating well past the old threshold must keep working."""
    headers = _auth_headers(client)
    for i in range(60):
        resp = client.post("/v1/scenarios", headers=headers, json={"name": f"Plan {i}"})
        assert resp.status_code == 201
