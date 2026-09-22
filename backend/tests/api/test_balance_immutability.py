"""Balance immutability (build spec §13.3 #5, D-04): PUT /me/balance is
the *only* write path for the Current Cash Balance. Everything else in
this test drives an arbitrary sequence of every other kind of write the
API exposes -- scenario, transaction, overlay, category, and settings
writes -- against one user, and asserts current_balance_minor /
balance_as_of never move. This is D-04 asserted rather than reviewed
for, the same way engine purity moved from a convention to a mechanical
check once import-linter existed.

Each Hypothesis example registers its own fresh user (unique email) and
never touches another example's rows, so -- same reasoning as
tests/services/test_scenario_resolver.py's isolation property -- the
function-scoped `client` fixture is safely shared across examples within
one test invocation.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.core.rate_limit import limiter


def _register(client: TestClient) -> dict[str, str]:
    # One `client` fixture instance is shared across every Hypothesis
    # example in this test (function-scoped, not example-scoped), and
    # TestClient reuses one fake client host for every request -- without
    # this, register's 5/min rate limit trips partway through the run,
    # since it's a limit meant for one real caller, not 25 unrelated
    # simulated users sharing a "connection."
    limiter.reset()
    email = f"immut-{uuid.uuid4()}@example.com"
    resp = client.post(
        "/v1/auth/register", json={"email": email, "password": "correct-horse", "name": "Test User"}
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@dataclass
class _State:
    base_id: str
    non_base_ids: list[str] = field(default_factory=list)
    archived_ids: set[str] = field(default_factory=set)
    base_txn_ids: list[str] = field(default_factory=list)
    overlays: list[tuple[str, str]] = field(default_factory=list)  # (scenario_id, overlay_id)
    category_ids: list[str] = field(default_factory=list)


def _patch_settings(client, headers, state, draw) -> None:
    client.patch(
        "/v1/me/settings",
        headers=headers,
        json={"locale": draw(st.sampled_from(["en", "ar"]))},
    )


def _create_scenario(client, headers, state, draw) -> None:
    resp = client.post(
        "/v1/scenarios", headers=headers, json={"name": f"Plan {uuid.uuid4().hex[:8]}"}
    )
    if resp.status_code == 201:
        state.non_base_ids.append(resp.json()["id"])


def _patch_scenario(client, headers, state, draw) -> None:
    sid = draw(st.sampled_from([state.base_id, *state.non_base_ids]))
    client.patch(
        f"/v1/scenarios/{sid}", headers=headers, json={"name": f"Renamed {uuid.uuid4().hex[:6]}"}
    )


def _archive_scenario(client, headers, state, draw) -> None:
    candidates = [s for s in state.non_base_ids if s not in state.archived_ids]
    sid = draw(st.sampled_from(candidates))
    resp = client.post(f"/v1/scenarios/{sid}/archive", headers=headers)
    if resp.status_code == 200:
        state.archived_ids.add(sid)


def _unarchive_scenario(client, headers, state, draw) -> None:
    sid = draw(st.sampled_from(sorted(state.archived_ids)))
    resp = client.post(f"/v1/scenarios/{sid}/unarchive", headers=headers)
    if resp.status_code == 200:
        state.archived_ids.discard(sid)


def _duplicate_scenario(client, headers, state, draw) -> None:
    sid = draw(st.sampled_from([state.base_id, *state.non_base_ids]))
    resp = client.post(f"/v1/scenarios/{sid}/duplicate", headers=headers, json={})
    if resp.status_code == 201:
        state.non_base_ids.append(resp.json()["id"])


def _delete_scenario(client, headers, state, draw) -> None:
    sid = draw(st.sampled_from(state.non_base_ids))
    resp = client.delete(f"/v1/scenarios/{sid}", headers=headers)
    if resp.status_code == 200:
        state.non_base_ids.remove(sid)
        state.archived_ids.discard(sid)


def _create_transaction(client, headers, state, draw) -> None:
    # Always on Base -- scenario-added transactions aren't tracked
    # separately, and Base's own rows are enough to exercise this write
    # path plus feed overlay creation below.
    resp = client.post(
        f"/v1/scenarios/{state.base_id}/transactions",
        headers=headers,
        json={
            "name": "Txn",
            "amount_minor": draw(st.integers(min_value=1, max_value=1_000_000)),
            "direction": draw(st.sampled_from(["income", "expense"])),
            "recurrence": "monthly",
            "start_date": "2026-01-01",
        },
    )
    if resp.status_code == 201:
        state.base_txn_ids.append(resp.json()["id"])


def _patch_transaction(client, headers, state, draw) -> None:
    tid = draw(st.sampled_from(state.base_txn_ids))
    client.patch(
        f"/v1/transactions/{tid}",
        headers=headers,
        json={"amount_minor": draw(st.integers(min_value=1, max_value=1_000_000))},
    )


def _delete_transaction(client, headers, state, draw) -> None:
    tid = draw(st.sampled_from(state.base_txn_ids))
    resp = client.delete(f"/v1/transactions/{tid}", headers=headers)
    if resp.status_code == 200:
        state.base_txn_ids.remove(tid)


def _create_overlay(client, headers, state, draw) -> None:
    sid = draw(st.sampled_from(state.non_base_ids))
    tid = draw(st.sampled_from(state.base_txn_ids))
    resp = client.post(
        f"/v1/scenarios/{sid}/overlays",
        headers=headers,
        json={"base_transaction_id": tid, "op": "exclude"},
    )
    if resp.status_code == 201:
        state.overlays.append((sid, resp.json()["id"]))


def _patch_overlay(client, headers, state, draw) -> None:
    sid, oid = draw(st.sampled_from(state.overlays))
    client.patch(f"/v1/scenarios/{sid}/overlays/{oid}", headers=headers, json={"ovr_name": "X"})


def _delete_overlay(client, headers, state, draw) -> None:
    sid, oid = draw(st.sampled_from(state.overlays))
    resp = client.delete(f"/v1/scenarios/{sid}/overlays/{oid}", headers=headers)
    if resp.status_code == 200:
        state.overlays.remove((sid, oid))


def _create_category(client, headers, state, draw) -> None:
    resp = client.post(
        "/v1/categories",
        headers=headers,
        json={
            "name": f"Cat {uuid.uuid4().hex[:8]}",
            "direction": draw(st.sampled_from(["income", "expense"])),
        },
    )
    if resp.status_code == 201:
        state.category_ids.append(resp.json()["id"])


def _patch_category(client, headers, state, draw) -> None:
    cid = draw(st.sampled_from(state.category_ids))
    client.patch(f"/v1/categories/{cid}", headers=headers, json={"name": "Renamed"})


def _delete_category(client, headers, state, draw) -> None:
    cid = draw(st.sampled_from(state.category_ids))
    resp = client.delete(f"/v1/categories/{cid}", headers=headers)
    if resp.status_code == 200:
        state.category_ids.remove(cid)


def _valid_actions(state: _State) -> list:
    actions = [_patch_settings, _create_scenario, _create_transaction, _create_category]
    actions.append(_patch_scenario)  # base always exists
    if state.non_base_ids:
        actions += [_duplicate_scenario, _delete_scenario]
    if [s for s in state.non_base_ids if s not in state.archived_ids]:
        actions.append(_archive_scenario)
    if state.archived_ids:
        actions.append(_unarchive_scenario)
    if state.base_txn_ids:
        actions += [_patch_transaction, _delete_transaction]
        if state.non_base_ids:
            actions.append(_create_overlay)
    if state.overlays:
        actions += [_patch_overlay, _delete_overlay]
    if state.category_ids:
        actions += [_patch_category, _delete_category]
    return actions


@given(data=st.data())
@settings(
    max_examples=25,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_balance_immutability_property(client: TestClient, data: st.DataObject) -> None:
    headers = _register(client)
    initial = client.get("/v1/me", headers=headers).json()["settings"]

    base_id = client.get("/v1/scenarios", headers=headers).json()["items"][0]["id"]
    state = _State(base_id=base_id)

    for _ in range(data.draw(st.integers(min_value=3, max_value=15))):
        action = data.draw(st.sampled_from(_valid_actions(state)))
        action(client, headers, state, data.draw)

    after = client.get("/v1/me", headers=headers).json()["settings"]
    assert after["current_balance_minor"] == initial["current_balance_minor"]
    assert after["balance_as_of"] == initial["balance_as_of"]
