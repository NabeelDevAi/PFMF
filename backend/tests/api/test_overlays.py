"""Overlay CRUD over HTTP: the critical editing flow from architecture
§9.2 / screen-flow §4.4, end to end through the resolved transactions
list -- there's no GET /overlays endpoint (architecture §9 has none; the
only way to see an overlay's effect is the resolved list, matching the
screen-flow's own UX)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _auth_headers(client: TestClient, email: str = "ovl@example.com") -> dict[str, str]:
    resp = client.post(
        "/v1/auth/register", json={"email": email, "password": "correct-horse", "name": "Test User"}
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _scenarios(client: TestClient, headers: dict) -> list[dict]:
    return client.get("/v1/scenarios", headers=headers).json()["items"]


def _base_id(client: TestClient, headers: dict) -> str:
    return next(s["id"] for s in _scenarios(client, headers) if s["is_base"])


def _add_base_transaction(client: TestClient, headers: dict, base_id: str, **overrides) -> dict:
    body = {
        "name": "Rent",
        "amount_minor": 300000,
        "direction": "expense",
        "recurrence": "monthly",
        "start_date": "2026-01-01",
        **overrides,
    }
    resp = client.post(f"/v1/scenarios/{base_id}/transactions", headers=headers, json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _resolved(client: TestClient, headers: dict, scenario_id: str) -> list[dict]:
    return client.get(f"/v1/scenarios/{scenario_id}/transactions", headers=headers).json()["items"]


def test_exclude_overlay_removes_transaction_from_resolved_list(client: TestClient) -> None:
    headers = _auth_headers(client)
    base_id = _base_id(client, headers)
    rent = _add_base_transaction(client, headers, base_id)
    plan = client.post("/v1/scenarios", headers=headers, json={"name": "Buy House"}).json()

    assert len(_resolved(client, headers, plan["id"])) == 1  # inherited before any overlay

    resp = client.post(
        f"/v1/scenarios/{plan['id']}/overlays",
        headers=headers,
        json={"base_transaction_id": rent["id"], "op": "exclude"},
    )
    assert resp.status_code == 201
    assert resp.json()["op"] == "exclude"

    assert _resolved(client, headers, plan["id"]) == []
    # Base itself is unaffected.
    assert len(_resolved(client, headers, base_id)) == 1


def test_override_overlay_patches_resolved_values(client: TestClient) -> None:
    headers = _auth_headers(client)
    base_id = _base_id(client, headers)
    rent = _add_base_transaction(client, headers, base_id)
    plan = client.post("/v1/scenarios", headers=headers, json={"name": "Buy House"}).json()

    resp = client.post(
        f"/v1/scenarios/{plan['id']}/overlays",
        headers=headers,
        json={"base_transaction_id": rent["id"], "op": "override", "ovr_amount_minor": 350000},
    )
    assert resp.status_code == 201
    overlay_id = resp.json()["id"]

    resolved = _resolved(client, headers, plan["id"])
    assert len(resolved) == 1
    assert resolved[0]["amount_minor"] == 350000
    assert resolved[0]["name"] == "Rent"  # untouched
    assert resolved[0]["origin"] == "overridden"
    assert resolved[0]["id"] == rent["id"]  # resolved identity is Base's transaction id
    # The client needs this to PATCH/DELETE .../overlays/{overlay_id} on a
    # row it's already looking at, without having to remember an id it
    # only ever saw once, back when the overlay was first created.
    assert resolved[0]["overlay_id"] == overlay_id

    # Base itself is unaffected.
    base_resolved = _resolved(client, headers, base_id)
    assert base_resolved[0]["amount_minor"] == 300000


def test_duplicate_overlay_for_same_target_is_conflict(client: TestClient) -> None:
    headers = _auth_headers(client)
    base_id = _base_id(client, headers)
    rent = _add_base_transaction(client, headers, base_id)
    plan = client.post("/v1/scenarios", headers=headers, json={"name": "Buy House"}).json()

    client.post(
        f"/v1/scenarios/{plan['id']}/overlays",
        headers=headers,
        json={"base_transaction_id": rent["id"], "op": "exclude"},
    )
    resp = client.post(
        f"/v1/scenarios/{plan['id']}/overlays",
        headers=headers,
        json={"base_transaction_id": rent["id"], "op": "override", "ovr_amount_minor": 1000},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "overlay.already_exists"


def test_overlay_cannot_target_a_transaction_outside_base(client: TestClient) -> None:
    headers = _auth_headers(client)
    base_id = _base_id(client, headers)
    plan = client.post("/v1/scenarios", headers=headers, json={"name": "Buy House"}).json()
    # A transaction that only exists in the derived plan, not Base.
    mortgage = _add_base_transaction(client, headers, plan["id"], name="Mortgage")

    resp = client.post(
        f"/v1/scenarios/{plan['id']}/overlays",
        headers=headers,
        json={"base_transaction_id": mortgage["id"], "op": "exclude"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "overlay.target_not_in_base"
    assert base_id  # sanity: base exists, this isn't a setup accident


def test_overlay_cannot_be_created_on_the_base_scenario_itself(client: TestClient) -> None:
    headers = _auth_headers(client)
    base_id = _base_id(client, headers)
    rent = _add_base_transaction(client, headers, base_id)

    resp = client.post(
        f"/v1/scenarios/{base_id}/overlays",
        headers=headers,
        json={"base_transaction_id": rent["id"], "op": "exclude"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "overlay.scenario_is_base"


def test_override_amount_not_positive_is_rejected(client: TestClient) -> None:
    headers = _auth_headers(client)
    base_id = _base_id(client, headers)
    rent = _add_base_transaction(client, headers, base_id)
    plan = client.post("/v1/scenarios", headers=headers, json={"name": "Buy House"}).json()

    resp = client.post(
        f"/v1/scenarios/{plan['id']}/overlays",
        headers=headers,
        json={"base_transaction_id": rent["id"], "op": "override", "ovr_amount_minor": 0},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "transaction.amount_not_positive"


def test_override_resulting_one_time_with_end_date_is_rejected(client: TestClient) -> None:
    headers = _auth_headers(client)
    base_id = _base_id(client, headers)
    rent = _add_base_transaction(client, headers, base_id)
    plan = client.post("/v1/scenarios", headers=headers, json={"name": "Buy House"}).json()

    resp = client.post(
        f"/v1/scenarios/{plan['id']}/overlays",
        headers=headers,
        json={
            "base_transaction_id": rent["id"],
            "op": "override",
            "ovr_recurrence": "one_time",
            "ovr_end_date": "2026-06-01",
        },
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "transaction.one_time_has_end_date"


def test_patch_overlay_updates_resolved_view(client: TestClient) -> None:
    headers = _auth_headers(client)
    base_id = _base_id(client, headers)
    rent = _add_base_transaction(client, headers, base_id)
    plan = client.post("/v1/scenarios", headers=headers, json={"name": "Buy House"}).json()
    created = client.post(
        f"/v1/scenarios/{plan['id']}/overlays",
        headers=headers,
        json={"base_transaction_id": rent["id"], "op": "override", "ovr_amount_minor": 350000},
    ).json()

    resp = client.patch(
        f"/v1/scenarios/{plan['id']}/overlays/{created['id']}",
        headers=headers,
        json={"ovr_amount_minor": 400000},
    )
    assert resp.status_code == 200
    assert resp.json()["ovr_amount_minor"] == 400000

    resolved = _resolved(client, headers, plan["id"])
    assert resolved[0]["amount_minor"] == 400000


def test_patch_overlay_unset_end_date_makes_it_open_ended(client: TestClient) -> None:
    headers = _auth_headers(client)
    base_id = _base_id(client, headers)
    rent = _add_base_transaction(client, headers, base_id, end_date="2026-12-01")
    plan = client.post("/v1/scenarios", headers=headers, json={"name": "Buy House"}).json()
    created = client.post(
        f"/v1/scenarios/{plan['id']}/overlays",
        headers=headers,
        json={"base_transaction_id": rent["id"], "op": "override", "ovr_amount_minor": 350000},
    ).json()
    assert _resolved(client, headers, plan["id"])[0]["end_date"] == "2026-12-01"

    resp = client.patch(
        f"/v1/scenarios/{plan['id']}/overlays/{created['id']}",
        headers=headers,
        json={"unset_end_date": True},
    )
    assert resp.status_code == 200
    assert resp.json()["unset_end_date"] is True

    resolved = _resolved(client, headers, plan["id"])
    assert resolved[0]["end_date"] is None

    # Base itself keeps its end_date.
    assert _resolved(client, headers, base_id)[0]["end_date"] == "2026-12-01"


def test_delete_overlay_reverts_to_inherited(client: TestClient) -> None:
    headers = _auth_headers(client)
    base_id = _base_id(client, headers)
    rent = _add_base_transaction(client, headers, base_id)
    plan = client.post("/v1/scenarios", headers=headers, json={"name": "Buy House"}).json()
    created = client.post(
        f"/v1/scenarios/{plan['id']}/overlays",
        headers=headers,
        json={"base_transaction_id": rent["id"], "op": "override", "ovr_amount_minor": 999999},
    ).json()

    resp = client.delete(f"/v1/scenarios/{plan['id']}/overlays/{created['id']}", headers=headers)
    assert resp.status_code == 200

    resolved = _resolved(client, headers, plan["id"])
    assert resolved[0]["amount_minor"] == 300000  # back to Base's value
    assert resolved[0]["origin"] == "inherited"


def test_delete_exclude_overlay_undoes_the_exclusion(client: TestClient) -> None:
    headers = _auth_headers(client)
    base_id = _base_id(client, headers)
    rent = _add_base_transaction(client, headers, base_id)
    plan = client.post("/v1/scenarios", headers=headers, json={"name": "Buy House"}).json()
    created = client.post(
        f"/v1/scenarios/{plan['id']}/overlays",
        headers=headers,
        json={"base_transaction_id": rent["id"], "op": "exclude"},
    ).json()
    assert _resolved(client, headers, plan["id"]) == []

    client.delete(f"/v1/scenarios/{plan['id']}/overlays/{created['id']}", headers=headers)
    resolved = _resolved(client, headers, plan["id"])
    assert len(resolved) == 1
    assert resolved[0]["origin"] == "inherited"


def test_removed_filter_shows_only_excluded_rows_with_overlay_id(client: TestClient) -> None:
    headers = _auth_headers(client)
    base_id = _base_id(client, headers)
    rent = _add_base_transaction(client, headers, base_id, name="Rent")
    groceries = _add_base_transaction(client, headers, base_id, name="Groceries")
    plan = client.post("/v1/scenarios", headers=headers, json={"name": "Buy House"}).json()

    excluded = client.post(
        f"/v1/scenarios/{plan['id']}/overlays",
        headers=headers,
        json={"base_transaction_id": rent["id"], "op": "exclude"},
    ).json()

    removed = client.get(
        f"/v1/scenarios/{plan['id']}/transactions",
        headers=headers,
        params={"filter": "removed"},
    ).json()["items"]
    assert len(removed) == 1
    assert removed[0]["id"] == rent["id"]
    assert removed[0]["name"] == "Rent"
    assert removed[0]["origin"] == "excluded"
    assert removed[0]["overlay_id"] == excluded["id"]

    # Groceries was never excluded -- it's active, not removed, and
    # shouldn't appear here at all.
    assert groceries["id"] not in {row["id"] for row in removed}

    # The default (and explicit "active") view still hides it entirely.
    active = _resolved(client, headers, plan["id"])
    assert rent["id"] not in {row["id"] for row in active}
    explicit_active = client.get(
        f"/v1/scenarios/{plan['id']}/transactions",
        headers=headers,
        params={"filter": "active"},
    ).json()["items"]
    assert rent["id"] not in {row["id"] for row in explicit_active}


def test_all_filter_combines_active_and_removed_rows(client: TestClient) -> None:
    headers = _auth_headers(client)
    base_id = _base_id(client, headers)
    rent = _add_base_transaction(client, headers, base_id, name="Rent")
    groceries = _add_base_transaction(client, headers, base_id, name="Groceries")
    plan = client.post("/v1/scenarios", headers=headers, json={"name": "Buy House"}).json()

    client.post(
        f"/v1/scenarios/{plan['id']}/overlays",
        headers=headers,
        json={"base_transaction_id": rent["id"], "op": "exclude"},
    )

    everything = client.get(
        f"/v1/scenarios/{plan['id']}/transactions", headers=headers, params={"filter": "all"}
    ).json()["items"]
    by_id = {row["id"]: row for row in everything}
    assert len(everything) == 2
    assert by_id[rent["id"]]["origin"] == "excluded"
    assert by_id[groceries["id"]]["origin"] == "inherited"
    assert by_id[groceries["id"]]["overlay_id"] is None  # no overlay on this row


def test_base_plan_ignores_removed_and_all_filters(client: TestClient) -> None:
    """Base can't exclude anything -- exclusion is a derived-scenario-only
    concept -- so every filter value behaves identically there."""
    headers = _auth_headers(client)
    base_id = _base_id(client, headers)
    _add_base_transaction(client, headers, base_id)

    for filter_value in ("active", "removed", "all"):
        items = client.get(
            f"/v1/scenarios/{base_id}/transactions",
            headers=headers,
            params={"filter": filter_value},
        ).json()["items"]
        if filter_value == "removed":
            assert items == []
        else:
            assert len(items) == 1
            assert items[0]["origin"] == "own"


def test_invalid_filter_value_is_rejected(client: TestClient) -> None:
    headers = _auth_headers(client)
    base_id = _base_id(client, headers)

    resp = client.get(
        f"/v1/scenarios/{base_id}/transactions", headers=headers, params={"filter": "bogus"}
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation.invalid"


def test_overlay_not_found_for_another_user_returns_404(client: TestClient) -> None:
    headers_a = _auth_headers(client, email="owner4@example.com")
    headers_b = _auth_headers(client, email="intruder4@example.com")
    base_id_a = _base_id(client, headers_a)
    rent = _add_base_transaction(client, headers_a, base_id_a)
    plan_a = client.post("/v1/scenarios", headers=headers_a, json={"name": "Buy House"}).json()
    overlay = client.post(
        f"/v1/scenarios/{plan_a['id']}/overlays",
        headers=headers_a,
        json={"base_transaction_id": rent["id"], "op": "exclude"},
    ).json()

    resp = client.patch(
        f"/v1/scenarios/{plan_a['id']}/overlays/{overlay['id']}",
        headers=headers_b,
        json={"ovr_name": "Hijacked"},
    )
    assert resp.status_code == 404

    resp = client.delete(
        f"/v1/scenarios/{plan_a['id']}/overlays/{overlay['id']}", headers=headers_b
    )
    assert resp.status_code == 404


def test_overlay_cannot_target_another_users_base_transaction(client: TestClient) -> None:
    """A well-formed but foreign base_transaction_id must not leak whether
    it exists -- same code as a target that simply doesn't exist."""
    headers_a = _auth_headers(client, email="owner5@example.com")
    headers_b = _auth_headers(client, email="intruder5@example.com")
    base_id_a = _base_id(client, headers_a)
    rent_a = _add_base_transaction(client, headers_a, base_id_a)
    plan_b = client.post("/v1/scenarios", headers=headers_b, json={"name": "B's plan"}).json()

    resp = client.post(
        f"/v1/scenarios/{plan_b['id']}/overlays",
        headers=headers_b,
        json={"base_transaction_id": rent_a["id"], "op": "exclude"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "overlay.target_not_in_base"
