"""GET /categories: system categories seeded by the data migration, plus
user-created ones. POST /categories: creating a user category. PATCH/DELETE
/categories/{id}: editing or removing a user category -- the two gaps
named in claude_docs/backend-plan/12-open-questions-and-future-hardening.md
§3 ("User category edit/delete are still not built -- only create.")."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _auth_headers(client: TestClient, email: str = "cats@example.com") -> dict[str, str]:
    resp = client.post("/v1/auth/register", json={"email": email, "password": "correct-horse"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_categories_requires_auth(client: TestClient) -> None:
    resp = client.get("/v1/categories")
    assert resp.status_code == 401


def test_categories_lists_seeded_system_categories(client: TestClient) -> None:
    headers = _auth_headers(client)

    resp = client.get("/v1/categories", headers=headers)
    assert resp.status_code == 200
    items = resp.json()["items"]

    keys = {c["key"] for c in items}
    assert "salary" in keys
    assert "rent" in keys
    assert all(c["user_id"] is None for c in items)  # none of these are user-created yet
    assert all(c["name"] is None for c in items)  # system categories carry key, not name

    directions = {c["key"]: c["direction"] for c in items}
    assert directions["salary"] == "income"
    assert directions["rent"] == "expense"


def test_create_category_requires_auth(client: TestClient) -> None:
    resp = client.post("/v1/categories", json={"name": "Side Hustle", "direction": "income"})
    assert resp.status_code == 401


def test_create_category_appears_in_the_list(client: TestClient) -> None:
    headers = _auth_headers(client, email="createcat@example.com")

    resp = client.post(
        "/v1/categories", headers=headers, json={"name": "Side Hustle", "direction": "income"}
    )
    assert resp.status_code == 201
    created = resp.json()
    assert created["name"] == "Side Hustle"
    assert created["key"] is None  # user categories carry name, not key
    assert created["direction"] == "income"
    assert created["user_id"] is not None

    items = client.get("/v1/categories", headers=headers).json()["items"]
    assert any(c["id"] == created["id"] for c in items)


def test_created_category_is_usable_on_a_transaction(client: TestClient) -> None:
    headers = _auth_headers(client, email="usecat@example.com")
    category = client.post(
        "/v1/categories", headers=headers, json={"name": "Gig work", "direction": "income"}
    ).json()
    base_id = client.get("/v1/scenarios", headers=headers).json()["items"][0]["id"]

    resp = client.post(
        f"/v1/scenarios/{base_id}/transactions",
        headers=headers,
        json={
            "name": "Freelance",
            "amount_minor": 50000,
            "direction": "income",
            "recurrence": "monthly",
            "start_date": "2026-01-01",
            "category_id": category["id"],
        },
    )
    assert resp.status_code == 201
    assert resp.json()["category_id"] == category["id"]


def test_a_users_category_is_not_visible_to_another_user(client: TestClient) -> None:
    headers_a = _auth_headers(client, email="catowner@example.com")
    headers_b = _auth_headers(client, email="catintruder@example.com")
    category = client.post(
        "/v1/categories", headers=headers_a, json={"name": "Private", "direction": "expense"}
    ).json()

    items_b = client.get("/v1/categories", headers=headers_b).json()["items"]
    assert all(c["id"] != category["id"] for c in items_b)

    # And it can't be used on B's own transaction either.
    base_id_b = client.get("/v1/scenarios", headers=headers_b).json()["items"][0]["id"]
    resp = client.post(
        f"/v1/scenarios/{base_id_b}/transactions",
        headers=headers_b,
        json={
            "name": "Rent",
            "amount_minor": 1000,
            "direction": "expense",
            "recurrence": "monthly",
            "start_date": "2026-01-01",
            "category_id": category["id"],
        },
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation.invalid"


def test_patch_category_requires_auth(client: TestClient) -> None:
    resp = client.patch("/v1/categories/00000000-0000-0000-0000-000000000000", json={"name": "x"})
    assert resp.status_code == 401


def test_patch_category_renames_and_changes_direction(client: TestClient) -> None:
    headers = _auth_headers(client, email="patchcat@example.com")
    category = client.post(
        "/v1/categories", headers=headers, json={"name": "Gig work", "direction": "income"}
    ).json()

    resp = client.patch(
        f"/v1/categories/{category['id']}",
        headers=headers,
        json={"name": "Side gigs", "direction": "expense"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Side gigs"
    assert body["direction"] == "expense"

    items = client.get("/v1/categories", headers=headers).json()["items"]
    patched = next(c for c in items if c["id"] == category["id"])
    assert patched["name"] == "Side gigs"
    assert patched["direction"] == "expense"


def test_patch_category_partial_update_only_touches_given_fields(client: TestClient) -> None:
    headers = _auth_headers(client, email="patchcat2@example.com")
    category = client.post(
        "/v1/categories", headers=headers, json={"name": "Gig work", "direction": "income"}
    ).json()

    resp = client.patch(
        f"/v1/categories/{category['id']}", headers=headers, json={"name": "Freelance"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Freelance"
    assert body["direction"] == "income"  # untouched


def test_patch_system_category_is_not_found(client: TestClient) -> None:
    headers = _auth_headers(client, email="patchsys@example.com")
    salary = next(
        c
        for c in client.get("/v1/categories", headers=headers).json()["items"]
        if c["key"] == "salary"
    )

    resp = client.patch(f"/v1/categories/{salary['id']}", headers=headers, json={"name": "Hacked"})
    assert resp.status_code == 404


def test_patch_another_users_category_is_not_found(client: TestClient) -> None:
    headers_a = _auth_headers(client, email="patchowner@example.com")
    headers_b = _auth_headers(client, email="patchintruder@example.com")
    category = client.post(
        "/v1/categories", headers=headers_a, json={"name": "Private", "direction": "expense"}
    ).json()

    resp = client.patch(
        f"/v1/categories/{category['id']}", headers=headers_b, json={"name": "Hijacked"}
    )
    assert resp.status_code == 404


def test_delete_category_requires_auth(client: TestClient) -> None:
    resp = client.delete("/v1/categories/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 401


def test_delete_unused_category_succeeds_and_disappears_from_the_list(client: TestClient) -> None:
    headers = _auth_headers(client, email="delcat@example.com")
    category = client.post(
        "/v1/categories", headers=headers, json={"name": "Throwaway", "direction": "expense"}
    ).json()

    resp = client.delete(f"/v1/categories/{category['id']}", headers=headers)
    assert resp.status_code == 204

    items = client.get("/v1/categories", headers=headers).json()["items"]
    assert all(c["id"] != category["id"] for c in items)


def test_delete_system_category_is_not_found(client: TestClient) -> None:
    headers = _auth_headers(client, email="delsys@example.com")
    salary = next(
        c
        for c in client.get("/v1/categories", headers=headers).json()["items"]
        if c["key"] == "salary"
    )

    resp = client.delete(f"/v1/categories/{salary['id']}", headers=headers)
    assert resp.status_code == 404


def test_delete_another_users_category_is_not_found(client: TestClient) -> None:
    headers_a = _auth_headers(client, email="delowner@example.com")
    headers_b = _auth_headers(client, email="delintruder@example.com")
    category = client.post(
        "/v1/categories", headers=headers_a, json={"name": "Private", "direction": "expense"}
    ).json()

    resp = client.delete(f"/v1/categories/{category['id']}", headers=headers_b)
    assert resp.status_code == 404


def test_delete_category_in_use_by_a_transaction_is_conflict(client: TestClient) -> None:
    headers = _auth_headers(client, email="delinuse@example.com")
    category = client.post(
        "/v1/categories", headers=headers, json={"name": "Gig work", "direction": "income"}
    ).json()
    base_id = client.get("/v1/scenarios", headers=headers).json()["items"][0]["id"]
    client.post(
        f"/v1/scenarios/{base_id}/transactions",
        headers=headers,
        json={
            "name": "Freelance",
            "amount_minor": 50000,
            "direction": "income",
            "recurrence": "monthly",
            "start_date": "2026-01-01",
            "category_id": category["id"],
        },
    )

    resp = client.delete(f"/v1/categories/{category['id']}", headers=headers)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "category.in_use"

    # Still there -- the failed delete must not have removed it anyway.
    items = client.get("/v1/categories", headers=headers).json()["items"]
    assert any(c["id"] == category["id"] for c in items)


def test_delete_category_in_use_by_an_overlay_is_conflict(client: TestClient) -> None:
    headers = _auth_headers(client, email="delinuse2@example.com")
    base_id = client.get("/v1/scenarios", headers=headers).json()["items"][0]["id"]
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
    category = client.post(
        "/v1/categories", headers=headers, json={"name": "Housing", "direction": "expense"}
    ).json()
    client.post(
        f"/v1/scenarios/{plan['id']}/overlays",
        headers=headers,
        json={
            "base_transaction_id": rent["id"],
            "op": "override",
            "ovr_category_id": category["id"],
        },
    )

    resp = client.delete(f"/v1/categories/{category['id']}", headers=headers)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "category.in_use"
