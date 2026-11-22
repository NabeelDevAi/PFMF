"""Custom recurrence over HTTP (UAT-004): "every N days/weeks/months/years"
on transactions and overlays, through validation, resolution, the forecast,
the month view, duplicate, export and the unsaved-rule preview."""

from __future__ import annotations

import csv
import io
import zipfile

import pytest
from fastapi.testclient import TestClient


def _auth_headers(client: TestClient, email: str) -> dict[str, str]:
    resp = client.post(
        "/v1/auth/register", json={"email": email, "password": "correct-horse", "name": "Test User"}
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _base_id(client: TestClient, headers: dict) -> str:
    items = client.get("/v1/scenarios", headers=headers).json()["items"]
    return next(s["id"] for s in items if s["is_base"])


def _post(client: TestClient, headers: dict, scenario_id: str, **overrides):
    body = {
        "name": "Rule",
        "amount_minor": 1000,
        "direction": "expense",
        "recurrence": "custom",
        "recurrence_interval": 4,
        "recurrence_unit": "month",
        "start_date": "2026-01-31",
        **overrides,
    }
    return client.post(f"/v1/scenarios/{scenario_id}/transactions", headers=headers, json=body)


def _field(resp) -> str:
    return resp.json()["error"]["params"]["field"]


def _forecast_dates(client: TestClient, headers: dict, sid: str, name: str, horizon: int):
    resp = client.get(
        f"/v1/scenarios/{sid}/forecast",
        headers=headers,
        params={"horizon": horizon, "anchor": "2026-01", "include_occurrences": True},
    )
    assert resp.status_code == 200, resp.text
    return [o["on"] for o in resp.json()["occurrences"] if o["name"] == name]


# ---- create and read back ----------------------------------------------------


@pytest.mark.parametrize("unit", ["day", "week", "month", "year"])
def test_create_custom_transaction_for_every_unit(client: TestClient, unit: str) -> None:
    headers = _auth_headers(client, f"cr-unit-{unit}@example.com")
    sid = _base_id(client, headers)

    resp = _post(client, headers, sid, recurrence_interval=3, recurrence_unit=unit)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert (body["recurrence"], body["recurrence_interval"], body["recurrence_unit"]) == (
        "custom",
        3,
        unit,
    )
    listed = client.get(f"/v1/scenarios/{sid}/transactions", headers=headers).json()["items"][0]
    assert (listed["recurrence_interval"], listed["recurrence_unit"]) == (3, unit)


def test_named_recurrences_have_no_interval_or_unit(client: TestClient) -> None:
    headers = _auth_headers(client, "cr-named@example.com")
    sid = _base_id(client, headers)
    resp = _post(
        client, headers, sid, recurrence="monthly", recurrence_interval=None, recurrence_unit=None
    )
    assert resp.status_code == 201
    assert resp.json()["recurrence_interval"] is None
    assert resp.json()["recurrence_unit"] is None


# ---- validation --------------------------------------------------------------


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"recurrence_interval": None}, "recurrence_interval"),
        ({"recurrence_unit": None}, "recurrence_unit"),
        ({"recurrence_interval": 0}, "recurrence_interval"),
        ({"recurrence_interval": -2}, "recurrence_interval"),
        ({"recurrence_interval": 1000}, "recurrence_interval"),
        ({"recurrence_interval": 2.5}, "recurrence_interval"),
        ({"recurrence_interval": "four"}, "recurrence_interval"),
        ({"recurrence_unit": "fortnight"}, "recurrence_unit"),
        ({"recurrence": "monthly"}, "recurrence_interval"),
        ({"recurrence": "weekly", "recurrence_interval": None}, "recurrence_unit"),
        ({"recurrence": "one_time", "recurrence_interval": None}, "recurrence_unit"),
    ],
)
def test_create_validation_matrix(client: TestClient, overrides: dict, field: str) -> None:
    headers = _auth_headers(client, "cr-val@example.com")
    sid = _base_id(client, headers)
    resp = _post(client, headers, sid, **overrides)
    assert resp.status_code == 422, resp.text
    assert resp.json()["error"]["code"] == "validation.invalid"
    assert _field(resp) == field


def test_interval_bounds_are_accepted(client: TestClient) -> None:
    headers = _auth_headers(client, "cr-bounds@example.com")
    sid = _base_id(client, headers)
    assert _post(client, headers, sid, recurrence_interval=1).status_code == 201
    assert _post(client, headers, sid, name="Max", recurrence_interval=999).status_code == 201


def test_custom_still_obeys_the_date_rules(client: TestClient) -> None:
    headers = _auth_headers(client, "cr-dates@example.com")
    sid = _base_id(client, headers)
    resp = _post(client, headers, sid, end_date="2026-01-01")
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "transaction.end_before_start"
    assert _post(client, headers, sid, end_date="2027-01-31").status_code == 201


# ---- patch -------------------------------------------------------------------


def test_patch_changes_only_the_interval_and_keeps_the_unit(client: TestClient) -> None:
    headers = _auth_headers(client, "cr-patch1@example.com")
    sid = _base_id(client, headers)
    txn = _post(client, headers, sid).json()

    resp = client.patch(
        f"/v1/transactions/{txn['id']}", headers=headers, json={"recurrence_interval": 6}
    )
    assert resp.status_code == 200
    assert (resp.json()["recurrence_interval"], resp.json()["recurrence_unit"]) == (6, "month")


def test_patch_to_custom_from_a_named_rule_needs_both_fields(client: TestClient) -> None:
    headers = _auth_headers(client, "cr-patch2@example.com")
    sid = _base_id(client, headers)
    txn = _post(
        client, headers, sid, recurrence="monthly", recurrence_interval=None, recurrence_unit=None
    ).json()

    missing = client.patch(
        f"/v1/transactions/{txn['id']}", headers=headers, json={"recurrence": "custom"}
    )
    assert missing.status_code == 422
    only_interval = client.patch(
        f"/v1/transactions/{txn['id']}",
        headers=headers,
        json={"recurrence": "custom", "recurrence_interval": 2},
    )
    assert only_interval.status_code == 422
    assert _field(only_interval) == "recurrence_unit"

    ok = client.patch(
        f"/v1/transactions/{txn['id']}",
        headers=headers,
        json={"recurrence": "custom", "recurrence_interval": 2, "recurrence_unit": "week"},
    )
    assert ok.status_code == 200
    assert (ok.json()["recurrence"], ok.json()["recurrence_interval"]) == ("custom", 2)


def test_patch_away_from_custom_clears_interval_and_unit(client: TestClient) -> None:
    headers = _auth_headers(client, "cr-patch3@example.com")
    sid = _base_id(client, headers)
    txn = _post(client, headers, sid).json()

    resp = client.patch(
        f"/v1/transactions/{txn['id']}", headers=headers, json={"recurrence": "quarterly"}
    )
    assert resp.status_code == 200
    assert resp.json()["recurrence"] == "quarterly"
    assert resp.json()["recurrence_interval"] is None
    assert resp.json()["recurrence_unit"] is None


def test_patch_sending_an_interval_with_a_named_rule_is_rejected(client: TestClient) -> None:
    headers = _auth_headers(client, "cr-patch4@example.com")
    sid = _base_id(client, headers)
    txn = _post(client, headers, sid).json()
    resp = client.patch(
        f"/v1/transactions/{txn['id']}",
        headers=headers,
        json={"recurrence": "monthly", "recurrence_interval": 3},
    )
    assert resp.status_code == 422
    assert _field(resp) == "recurrence_interval"


def test_patch_interval_on_a_non_custom_transaction_is_rejected(client: TestClient) -> None:
    headers = _auth_headers(client, "cr-patch5@example.com")
    sid = _base_id(client, headers)
    txn = _post(
        client, headers, sid, recurrence="monthly", recurrence_interval=None, recurrence_unit=None
    ).json()
    resp = client.patch(
        f"/v1/transactions/{txn['id']}", headers=headers, json={"recurrence_interval": 3}
    )
    assert resp.status_code == 422


# ---- forecast and month view ---------------------------------------------------


def test_forecast_expands_the_clients_examples(client: TestClient) -> None:
    headers = _auth_headers(client, "cr-fc@example.com")
    sid = _base_id(client, headers)
    _post(
        client,
        headers,
        sid,
        name="Ten days",
        recurrence_interval=10,
        recurrence_unit="day",
        start_date="2026-01-01",
    )
    _post(client, headers, sid, name="Four months", start_date="2026-01-31")
    _post(
        client,
        headers,
        sid,
        name="Two years",
        recurrence_interval=2,
        recurrence_unit="year",
        start_date="2024-02-29",
    )

    assert _forecast_dates(client, headers, sid, "Ten days", 2)[:4] == [
        "2026-01-01",
        "2026-01-11",
        "2026-01-21",
        "2026-01-31",
    ]
    assert _forecast_dates(client, headers, sid, "Four months", 12) == [
        "2026-01-31",
        "2026-05-31",
        "2026-09-30",
    ]
    assert _forecast_dates(client, headers, sid, "Two years", 36) == ["2026-02-28", "2028-02-29"]


def test_month_view_shows_custom_due_dates_and_the_rule(client: TestClient) -> None:
    headers = _auth_headers(client, "cr-month@example.com")
    sid = _base_id(client, headers)
    _post(
        client,
        headers,
        sid,
        name="Every 10 days",
        recurrence_interval=10,
        recurrence_unit="day",
        start_date="2026-01-01",
    )
    body = client.get(
        f"/v1/scenarios/{sid}/occurrences", headers=headers, params={"month": "2026-02"}
    ).json()
    assert [i["on"] for i in body["items"]] == ["2026-02-10", "2026-02-20"]
    assert body["totals"]["expense_minor"] == 2000
    first = body["items"][0]
    assert (first["recurrence"], first["recurrence_interval"], first["recurrence_unit"]) == (
        "custom",
        10,
        "day",
    )
    assert first["start_date"] == "2026-01-01"


# ---- overlays (derived plans) --------------------------------------------------


def _plan(client: TestClient, headers: dict, name: str = "Plan") -> dict:
    return client.post("/v1/scenarios", headers=headers, json={"name": [name]}).json()["items"][0]


def _overlay(client: TestClient, headers: dict, plan_id: str, base_txn_id: str, **fields):
    return client.post(
        f"/v1/scenarios/{plan_id}/overlays",
        headers=headers,
        json={"base_transaction_id": base_txn_id, "op": "override", **fields},
    )


def _resolved(client: TestClient, headers: dict, plan_id: str, name: str) -> dict:
    items = client.get(f"/v1/scenarios/{plan_id}/transactions", headers=headers).json()["items"]
    return next(i for i in items if i["name"] == name)


def test_overlay_can_override_a_monthly_item_to_custom_and_base_is_untouched(
    client: TestClient,
) -> None:
    headers = _auth_headers(client, "cr-ov1@example.com")
    base_id = _base_id(client, headers)
    base_txn = _post(
        client,
        headers,
        base_id,
        name="Gym",
        recurrence="monthly",
        recurrence_interval=None,
        recurrence_unit=None,
        start_date="2026-01-10",
    ).json()
    plan = _plan(client, headers)

    resp = _overlay(
        client,
        headers,
        plan["id"],
        base_txn["id"],
        ovr_recurrence="custom",
        ovr_recurrence_interval=2,
        ovr_recurrence_unit="week",
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["ovr_recurrence_interval"] == 2

    row = _resolved(client, headers, plan["id"], "Gym")
    assert (row["recurrence"], row["recurrence_interval"], row["recurrence_unit"]) == (
        "custom",
        2,
        "week",
    )
    assert row["origin"] == "overridden"
    assert _forecast_dates(client, headers, plan["id"], "Gym", 1) == [
        "2026-01-10",
        "2026-01-24",
    ]
    # Base itself is unchanged.
    base_row = _resolved(client, headers, base_id, "Gym")
    assert (base_row["recurrence"], base_row["recurrence_interval"]) == ("monthly", None)


def test_overlay_can_override_a_custom_item_back_to_a_named_rule(client: TestClient) -> None:
    headers = _auth_headers(client, "cr-ov2@example.com")
    base_id = _base_id(client, headers)
    base_txn = _post(client, headers, base_id, name="Course").json()  # custom, every 4 months
    plan = _plan(client, headers)

    resp = _overlay(client, headers, plan["id"], base_txn["id"], ovr_recurrence="annual")
    assert resp.status_code == 201
    row = _resolved(client, headers, plan["id"], "Course")
    assert row["recurrence"] == "annual"
    assert row["recurrence_interval"] is None and row["recurrence_unit"] is None


def test_overlay_that_does_not_touch_recurrence_keeps_the_base_custom_rule(
    client: TestClient,
) -> None:
    headers = _auth_headers(client, "cr-ov3@example.com")
    base_id = _base_id(client, headers)
    base_txn = _post(client, headers, base_id, name="Course").json()
    plan = _plan(client, headers)

    _overlay(client, headers, plan["id"], base_txn["id"], ovr_amount_minor=5000)
    row = _resolved(client, headers, plan["id"], "Course")
    assert row["amount_minor"] == 5000
    assert (row["recurrence"], row["recurrence_interval"], row["recurrence_unit"]) == (
        "custom",
        4,
        "month",
    )


@pytest.mark.parametrize(
    ("fields", "field"),
    [
        ({"ovr_recurrence_interval": 3}, "ovr_recurrence_interval"),
        ({"ovr_recurrence_unit": "day"}, "ovr_recurrence_unit"),
        ({"ovr_recurrence": "custom"}, "ovr_recurrence_interval"),
        (
            {"ovr_recurrence": "custom", "ovr_recurrence_interval": 3},
            "ovr_recurrence_unit",
        ),
        (
            {
                "ovr_recurrence": "custom",
                "ovr_recurrence_interval": 0,
                "ovr_recurrence_unit": "day",
            },
            "ovr_recurrence_interval",
        ),
        (
            {"ovr_recurrence": "monthly", "ovr_recurrence_interval": 3},
            "ovr_recurrence_interval",
        ),
    ],
)
def test_overlay_create_validation(client: TestClient, fields: dict, field: str) -> None:
    headers = _auth_headers(client, "cr-ov4@example.com")
    base_id = _base_id(client, headers)
    base_txn = _post(client, headers, base_id, name="Course").json()
    plan = _plan(client, headers)

    resp = _overlay(client, headers, plan["id"], base_txn["id"], **fields)
    assert resp.status_code == 422, resp.text
    assert _field(resp) == field


def test_overlay_patch_updates_interval_and_switching_away_clears_it(client: TestClient) -> None:
    headers = _auth_headers(client, "cr-ov5@example.com")
    base_id = _base_id(client, headers)
    base_txn = _post(client, headers, base_id, name="Course").json()
    plan = _plan(client, headers)
    overlay = _overlay(
        client,
        headers,
        plan["id"],
        base_txn["id"],
        ovr_recurrence="custom",
        ovr_recurrence_interval=2,
        ovr_recurrence_unit="year",
    ).json()
    url = f"/v1/scenarios/{plan['id']}/overlays/{overlay['id']}"

    updated = client.patch(url, headers=headers, json={"ovr_recurrence_interval": 3}).json()
    assert (updated["ovr_recurrence_interval"], updated["ovr_recurrence_unit"]) == (3, "year")

    cleared = client.patch(url, headers=headers, json={"ovr_recurrence": "quarterly"}).json()
    assert cleared["ovr_recurrence"] == "quarterly"
    assert cleared["ovr_recurrence_interval"] is None
    assert cleared["ovr_recurrence_unit"] is None

    again = client.patch(
        url,
        headers=headers,
        json={
            "ovr_recurrence": "custom",
            "ovr_recurrence_interval": 5,
            "ovr_recurrence_unit": "day",
        },
    ).json()
    assert (again["ovr_recurrence_interval"], again["ovr_recurrence_unit"]) == (5, "day")


def test_overlay_patch_interval_without_an_overridden_recurrence_is_rejected(
    client: TestClient,
) -> None:
    headers = _auth_headers(client, "cr-ov6@example.com")
    base_id = _base_id(client, headers)
    base_txn = _post(client, headers, base_id, name="Course").json()
    plan = _plan(client, headers)
    overlay = _overlay(client, headers, plan["id"], base_txn["id"], ovr_amount_minor=1).json()

    resp = client.patch(
        f"/v1/scenarios/{plan['id']}/overlays/{overlay['id']}",
        headers=headers,
        json={"ovr_recurrence_interval": 3},
    )
    assert resp.status_code == 422
    assert _field(resp) == "ovr_recurrence_interval"


# ---- duplicate ---------------------------------------------------------------


def test_duplicate_copies_custom_transactions_and_custom_overlays(client: TestClient) -> None:
    headers = _auth_headers(client, "cr-dup@example.com")
    base_id = _base_id(client, headers)
    inherited = _post(
        client,
        headers,
        base_id,
        name="Inherited",
        recurrence="monthly",
        recurrence_interval=None,
        recurrence_unit=None,
    ).json()
    plan = _plan(client, headers, "Source")
    _post(
        client,
        headers,
        plan["id"],
        name="Own custom",
        recurrence_interval=10,
        recurrence_unit="day",
        start_date="2026-01-01",
    )
    _overlay(
        client,
        headers,
        plan["id"],
        inherited["id"],
        ovr_recurrence="custom",
        ovr_recurrence_interval=3,
        ovr_recurrence_unit="week",
    )

    copy = client.post(
        f"/v1/scenarios/{plan['id']}/duplicate", headers=headers, json={"name": "Copy"}
    ).json()

    own = _resolved(client, headers, copy["id"], "Own custom")
    assert (own["recurrence"], own["recurrence_interval"], own["recurrence_unit"]) == (
        "custom",
        10,
        "day",
    )
    over = _resolved(client, headers, copy["id"], "Inherited")
    assert (over["recurrence"], over["recurrence_interval"], over["recurrence_unit"]) == (
        "custom",
        3,
        "week",
    )
    # Independent: changing the copy's own item leaves the source alone.
    client.patch(f"/v1/transactions/{own['id']}", headers=headers, json={"recurrence_interval": 20})
    assert _resolved(client, headers, plan["id"], "Own custom")["recurrence_interval"] == 10
    # The copied override really drives the copy's forecast: every 3 weeks
    # from the base item's start date (2026-01-31).
    assert _forecast_dates(client, headers, copy["id"], "Inherited", 2) == [
        "2026-01-31",
        "2026-02-21",
    ]


# ---- export ------------------------------------------------------------------


def test_export_includes_the_custom_fields(client: TestClient) -> None:
    headers = _auth_headers(client, "cr-exp@example.com")
    base_id = _base_id(client, headers)
    base_txn = _post(client, headers, base_id, name="Course").json()
    plan = _plan(client, headers)
    _overlay(
        client,
        headers,
        plan["id"],
        base_txn["id"],
        ovr_recurrence="custom",
        ovr_recurrence_interval=2,
        ovr_recurrence_unit="year",
    )

    data = client.get("/v1/me/export", headers=headers).json()
    txn = next(t for t in data["transactions"] if t["name"] == "Course")
    assert (txn["recurrence"], txn["recurrence_interval"], txn["recurrence_unit"]) == (
        "custom",
        4,
        "month",
    )
    assert data["overlays"][0]["ovr_recurrence_interval"] == 2
    assert data["overlays"][0]["ovr_recurrence_unit"] == "year"

    zipped = client.get("/v1/me/export", headers=headers, params={"format": "csv"})
    assert zipped.status_code == 200
    with zipfile.ZipFile(io.BytesIO(zipped.content)) as zf:
        rows = list(csv.DictReader(io.StringIO(zf.read("transactions.csv").decode())))
        overlay_rows = list(csv.DictReader(io.StringIO(zf.read("overlays.csv").decode())))
    assert (rows[0]["recurrence_interval"], rows[0]["recurrence_unit"]) == ("4", "month")
    assert (overlay_rows[0]["ovr_recurrence_interval"], overlay_rows[0]["ovr_recurrence_unit"]) == (
        "2",
        "year",
    )


# ---- preview endpoint --------------------------------------------------------


def _preview(client: TestClient, headers: dict | None, **body):
    payload = {
        "recurrence": "custom",
        "recurrence_interval": 4,
        "recurrence_unit": "month",
        "start_date": "2026-01-31",
        **body,
    }
    return client.post("/v1/transactions/preview-occurrences", headers=headers, json=payload)


def test_preview_returns_the_next_dates_with_the_clamp_rule(client: TestClient) -> None:
    headers = _auth_headers(client, "cr-prev1@example.com")
    resp = _preview(client, headers, count=5)
    assert resp.status_code == 200
    assert resp.json()["dates"] == [
        "2026-01-31",
        "2026-05-31",
        "2026-09-30",
        "2027-01-31",
        "2027-05-31",
    ]


def test_preview_default_count_is_six_and_the_maximum_is_24(client: TestClient) -> None:
    headers = _auth_headers(client, "cr-prev2@example.com")
    assert len(_preview(client, headers).json()["dates"]) == 6
    assert len(_preview(client, headers, count=24).json()["dates"]) == 24
    assert _preview(client, headers, count=25).status_code == 422
    assert _preview(client, headers, count=0).status_code == 422


def test_preview_stops_at_the_end_date(client: TestClient) -> None:
    headers = _auth_headers(client, "cr-prev3@example.com")
    resp = _preview(
        client,
        headers,
        recurrence_interval=10,
        recurrence_unit="day",
        start_date="2026-01-01",
        end_date="2026-01-25",
    )
    assert resp.json()["dates"] == ["2026-01-01", "2026-01-11", "2026-01-21"]


def test_preview_works_for_named_and_one_time_rules(client: TestClient) -> None:
    headers = _auth_headers(client, "cr-prev4@example.com")
    monthly = _preview(
        client,
        headers,
        recurrence="monthly",
        recurrence_interval=None,
        recurrence_unit=None,
        start_date="2026-01-31",
        count=3,
    )
    assert monthly.json()["dates"] == ["2026-01-31", "2026-02-28", "2026-03-31"]
    once = _preview(
        client,
        headers,
        recurrence="one_time",
        recurrence_interval=None,
        recurrence_unit=None,
        start_date="2026-03-15",
    )
    assert once.json()["dates"] == ["2026-03-15"]


def test_preview_matches_what_the_forecast_produces(client: TestClient) -> None:
    headers = _auth_headers(client, "cr-prev5@example.com")
    sid = _base_id(client, headers)
    _post(
        client,
        headers,
        sid,
        name="Match",
        recurrence_interval=45,
        recurrence_unit="day",
        start_date="2026-01-07",
    )
    previewed = _preview(
        client,
        headers,
        recurrence_interval=45,
        recurrence_unit="day",
        start_date="2026-01-07",
        count=8,
    ).json()["dates"]
    assert _forecast_dates(client, headers, sid, "Match", 12)[:8] == previewed


@pytest.mark.parametrize(
    ("body", "code", "field"),
    [
        ({"recurrence_interval": None}, "validation.invalid", "recurrence_interval"),
        ({"recurrence_interval": 0}, "validation.invalid", "recurrence_interval"),
        ({"recurrence_unit": None}, "validation.invalid", "recurrence_unit"),
        ({"recurrence": "monthly"}, "validation.invalid", "recurrence_interval"),
        ({"start_date": "1999-01-01"}, "validation.invalid", "start_date"),
        ({"end_date": "2025-01-01"}, "transaction.end_before_start", "end_date"),
        (
            {
                "recurrence": "one_time",
                "recurrence_interval": None,
                "recurrence_unit": None,
                "end_date": "2027-01-01",
            },
            "transaction.one_time_has_end_date",
            "end_date",
        ),
    ],
)
def test_preview_validation(client: TestClient, body: dict, code: str, field: str) -> None:
    headers = _auth_headers(client, "cr-prev6@example.com")
    resp = _preview(client, headers, **body)
    assert resp.status_code == 422, resp.text
    assert resp.json()["error"]["code"] == code
    assert _field(resp) == field


def test_preview_requires_authentication(client: TestClient) -> None:
    assert _preview(client, None).status_code == 401
