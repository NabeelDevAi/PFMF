"""GET /scenarios/{id}/occurrences?month= (UAT-007): the month view's data."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.api.uat_examples import CLIENT_EXAMPLES, EXPECTED_DUE_DATES, EXPECTED_MONTHS


def _auth_headers(client: TestClient, email: str) -> dict[str, str]:
    resp = client.post(
        "/v1/auth/register", json={"email": email, "password": "correct-horse", "name": "Test User"}
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _base_id(client: TestClient, headers: dict) -> str:
    items = client.get("/v1/scenarios", headers=headers).json()["items"]
    return next(s["id"] for s in items if s["is_base"])


def _add(client: TestClient, headers: dict, scenario_id: str, **body) -> dict:
    resp = client.post(f"/v1/scenarios/{scenario_id}/transactions", headers=headers, json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _load_client_examples(client: TestClient, headers: dict, scenario_id: str) -> dict[str, dict]:
    created = {}
    for name, amount, direction, recurrence, start, end in CLIENT_EXAMPLES:
        body = {
            "name": name,
            "amount_minor": amount,
            "direction": direction,
            "recurrence": recurrence,
            "start_date": start,
        }
        if end:
            body["end_date"] = end
        created[name] = _add(client, headers, scenario_id, **body)
    return created


def _month(client: TestClient, headers: dict, scenario_id: str, month: str):
    return client.get(
        f"/v1/scenarios/{scenario_id}/occurrences", headers=headers, params={"month": month}
    )


def _totals(body: dict) -> tuple[int, int, int]:
    t = body["totals"]
    return t["income_minor"], t["expense_minor"], t["net_minor"]


def _forecast_rows(client: TestClient, headers: dict, scenario_id: str) -> dict[str, dict]:
    resp = client.get(
        f"/v1/scenarios/{scenario_id}/forecast",
        headers=headers,
        params={"horizon": 6, "anchor": "2026-11"},
    )
    assert resp.status_code == 200
    return {m["month"]: m for m in resp.json()["months"]}


# ---- the client's own examples ----------------------------------------------


def test_client_examples_month_totals_match_the_calculated_table(client: TestClient) -> None:
    headers = _auth_headers(client, "occ1@example.com")
    sid = _base_id(client, headers)
    _load_client_examples(client, headers, sid)

    for month, expected in EXPECTED_MONTHS.items():
        resp = _month(client, headers, sid, month)
        assert resp.status_code == 200, month
        body = resp.json()
        assert body["month"] == month
        assert _totals(body) == expected, month


def test_client_examples_show_each_recurring_item_on_its_own_due_date(client: TestClient) -> None:
    headers = _auth_headers(client, "occ2@example.com")
    sid = _base_id(client, headers)
    _load_client_examples(client, headers, sid)
    recurring = {"Kaytus Salary", "Driver Salary", "Personal Loan", "SEC", "Telco", "Maid Salary"}

    for month, expected_dates in EXPECTED_DUE_DATES.items():
        items = _month(client, headers, sid, month).json()["items"]
        dates = {i["name"]: i["on"] for i in items if i["name"] in recurring}
        assert dates == expected_dates, month


def test_january_shows_the_january_due_date_not_the_november_series_start(
    client: TestClient,
) -> None:
    headers = _auth_headers(client, "occ3@example.com")
    sid = _base_id(client, headers)
    _load_client_examples(client, headers, sid)

    kaytus = next(
        i
        for i in _month(client, headers, sid, "2027-01").json()["items"]
        if i["name"] == "Kaytus Salary"
    )
    assert kaytus["on"] == "2027-01-22"
    assert kaytus["start_date"] == "2026-11-22"  # the series start is a separate field
    assert kaytus["end_date"] is None
    assert kaytus["recurrence"] == "monthly"


def test_personal_loan_runs_nov_to_mar_and_is_absent_in_april(client: TestClient) -> None:
    headers = _auth_headers(client, "occ4@example.com")
    sid = _base_id(client, headers)
    _load_client_examples(client, headers, sid)

    def loan_dates(month: str) -> list[str]:
        items = _month(client, headers, sid, month).json()["items"]
        return [i["on"] for i in items if i["name"] == "Personal Loan"]

    assert loan_dates("2027-03") == ["2027-03-19"]
    assert loan_dates("2027-04") == []
    assert loan_dates("2026-10") == []  # before the series starts


def test_one_time_examples_appear_only_in_their_own_month(client: TestClient) -> None:
    headers = _auth_headers(client, "occ5@example.com")
    sid = _base_id(client, headers)
    _load_client_examples(client, headers, sid)
    one_time = {
        "Gitex Kay": "2026-11",
        "Stock 2": "2026-12",
        "BMW": "2026-12",
        "Binghatti": "2026-12",
    }

    for month in ("2026-10", "2026-11", "2026-12", "2027-01", "2027-02"):
        names = {i["name"] for i in _month(client, headers, sid, month).json()["items"]}
        for name, own_month in one_time.items():
            assert (name in names) == (month == own_month), (name, month)


def test_month_totals_equal_the_forecast_rows_for_the_same_months(client: TestClient) -> None:
    headers = _auth_headers(client, "occ6@example.com")
    sid = _base_id(client, headers)
    _load_client_examples(client, headers, sid)
    rows = _forecast_rows(client, headers, sid)

    for month, row in rows.items():
        body = _month(client, headers, sid, month).json()
        assert _totals(body) == (row["income_minor"], row["expense_minor"], row["net_minor"])


def test_derived_plan_with_an_exclusion_and_an_override_reconciles_with_its_forecast(
    client: TestClient,
) -> None:
    headers = _auth_headers(client, "occ7@example.com")
    base_id = _base_id(client, headers)
    created = _load_client_examples(client, headers, base_id)
    plan = client.post("/v1/scenarios", headers=headers, json={"name": ["Variant"]}).json()[
        "items"
    ][0]
    # Exclude the Maid Salary, and override the Telco amount, in the plan only.
    client.post(
        f"/v1/scenarios/{plan['id']}/overlays",
        headers=headers,
        json={"base_transaction_id": created["Maid Salary"]["id"], "op": "exclude"},
    )
    client.post(
        f"/v1/scenarios/{plan['id']}/overlays",
        headers=headers,
        json={
            "base_transaction_id": created["Telco"]["id"],
            "op": "override",
            "ovr_amount_minor": 250_000,
        },
    )

    body = _month(client, headers, plan["id"], "2027-01").json()
    names = {i["name"] for i in body["items"]}
    assert "Maid Salary" not in names
    telco = next(i for i in body["items"] if i["name"] == "Telco")
    assert telco["amount_minor"] == 250_000
    assert telco["origin"] == "overridden"
    # Base expense 2,635,811 - Maid 150,000 + Telco change 50,000
    assert _totals(body) == (9_611_250, 2_535_811, 7_075_439)
    # Base itself is unchanged.
    assert _totals(_month(client, headers, base_id, "2027-01").json()) == EXPECTED_MONTHS["2027-01"]

    rows = _forecast_rows(client, headers, plan["id"])
    for month, row in rows.items():
        got = _totals(_month(client, headers, plan["id"], month).json())
        assert got == (row["income_minor"], row["expense_minor"], row["net_minor"]), month


# ---- shape, ordering and edge cases -----------------------------------------


def test_items_are_sorted_by_date_then_name_and_carry_the_documented_fields(
    client: TestClient,
) -> None:
    headers = _auth_headers(client, "occ8@example.com")
    sid = _base_id(client, headers)
    created = _load_client_examples(client, headers, sid)

    body = _month(client, headers, sid, "2026-12").json()
    items = body["items"]
    assert [(i["on"], i["name"]) for i in items] == sorted((i["on"], i["name"]) for i in items)
    assert body["currency_code"] == "SAR"
    stock = next(i for i in items if i["name"] == "Stock 2")
    assert stock == {
        "transaction_id": created["Stock 2"]["id"],
        "name": "Stock 2",
        "direction": "income",
        "amount_minor": 482_800,
        "on": "2026-12-09",
        "origin": "own",
        "recurrence": "one_time",
        "start_date": "2026-12-09",
        "end_date": None,
        "category_id": None,
    }


def test_a_month_with_nothing_scheduled_returns_empty_items_and_zero_totals(
    client: TestClient,
) -> None:
    headers = _auth_headers(client, "occ9@example.com")
    sid = _base_id(client, headers)
    body = _month(client, headers, sid, "2026-11").json()
    assert body["items"] == []
    assert _totals(body) == (0, 0, 0)


def test_day_31_item_is_clamped_in_short_months(client: TestClient) -> None:
    headers = _auth_headers(client, "occ10@example.com")
    sid = _base_id(client, headers)
    _add(
        client,
        headers,
        sid,
        name="Month end",
        amount_minor=1000,
        direction="expense",
        recurrence="monthly",
        start_date="2026-01-31",
    )
    assert _month(client, headers, sid, "2027-02").json()["items"][0]["on"] == "2027-02-28"
    assert _month(client, headers, sid, "2028-02").json()["items"][0]["on"] == "2028-02-29"
    assert _month(client, headers, sid, "2027-04").json()["items"][0]["on"] == "2027-04-30"


def test_months_before_the_balance_month_can_be_browsed(client: TestClient) -> None:
    headers = _auth_headers(client, "occ11@example.com")
    sid = _base_id(client, headers)
    _add(
        client,
        headers,
        sid,
        name="Old rent",
        amount_minor=1000,
        direction="expense",
        recurrence="monthly",
        start_date="2024-03-05",
    )
    resp = _month(client, headers, sid, "2025-06")
    assert resp.status_code == 200
    assert [i["on"] for i in resp.json()["items"]] == ["2025-06-05"]


# ---- validation, range, auth ------------------------------------------------


def test_invalid_missing_and_out_of_range_months_are_rejected(client: TestClient) -> None:
    headers = _auth_headers(client, "occ12@example.com")
    sid = _base_id(client, headers)

    for bad in ("2026-13", "2026-00", "nonsense", "2026", "2026-1-1", ""):
        resp = _month(client, headers, sid, bad)
        assert resp.status_code == 422, bad
        assert resp.json()["error"]["code"] == "validation.invalid", bad

    missing = client.get(f"/v1/scenarios/{sid}/occurrences", headers=headers)
    assert missing.status_code == 422
    assert missing.json()["error"]["code"] == "validation.required"

    # More than 120 months either side of the balance month.
    assert _month(client, headers, sid, "2100-01").status_code == 422
    assert _month(client, headers, sid, "2000-01").status_code == 422


def test_occurrences_require_auth_and_respect_ownership(client: TestClient) -> None:
    headers = _auth_headers(client, "occ13@example.com")
    sid = _base_id(client, headers)
    other = _auth_headers(client, "occ13b@example.com")

    assert (
        client.get(f"/v1/scenarios/{sid}/occurrences", params={"month": "2026-11"}).status_code
        == 401
    )
    assert _month(client, other, sid, "2026-11").status_code == 404
    unknown = "00000000-0000-0000-0000-000000000000"
    assert _month(client, headers, unknown, "2026-11").status_code == 404
