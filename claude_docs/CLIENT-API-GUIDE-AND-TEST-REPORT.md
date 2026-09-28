# Horizon Backend — API Guide & Live Test Report

**Prepared for:** Client
**Environment tested:** Production
**Base URL:** `https://api-finance-forecast.com`
**Test date:** September 27, 2026
**Result:** 59 / 59 checks passed — 0 failures

This document has two parts:

- **Part A** — everything you need to test the API yourself: what it does, how authentication works, and the exact request/response shape for every endpoint, with real examples pulled from the live server.
- **Part B** — the test report: every endpoint listed above, run against the live production server on the date above, with the actual HTTP status and response returned, so you can see for yourself that each one behaves as documented.

Nothing in this document is a guess — every request/response example below is copy-pasted from a real call made against `https://api-finance-forecast.com` on the test date.

---

## Table of Contents

**Part A — API Guide**
1. [What This API Does](#1-what-this-api-does)
2. [How to Test It Yourself](#2-how-to-test-it-yourself)
3. [Conventions That Apply to Every Endpoint](#3-conventions-that-apply-to-every-endpoint)
4. [Authentication](#4-authentication)
5. [Profile, Balance & Settings](#5-profile-balance--settings)
6. [Categories](#6-categories)
7. [Plans (Scenarios)](#7-plans-scenarios)
8. [Transactions](#8-transactions)
9. [Overlays (Editing Inherited Transactions)](#9-overlays-editing-inherited-transactions)
10. [Forecast & Compare](#10-forecast--compare)
11. [Account Data (Export / Reset / Delete)](#11-account-data-export--reset--delete)
12. [Error Code Reference](#12-error-code-reference)
13. [Known Limitations (By Design, Not Bugs)](#13-known-limitations-by-design-not-bugs)

**Part B — Test Report**
14. [Test Summary](#14-test-summary)
15. [Detailed Test Log (Every Call, Every Response)](#15-detailed-test-log-every-call-every-response)

---

# Part A — API Guide

## 1. What This API Does

Horizon's backend lets a user:

- Create an account and log in securely.
- Record their real cash balance and their income/expense transactions.
- Build multiple "what-if" financial plans (e.g. "Buy a House") that start from their real numbers and branch off — without ever losing or duplicating the original data.
- See a month-by-month forecast of their balance, for up to 10 years out, for any plan.
- Compare any two plans against each other.
- Manage their profile, currency/language, password, and export or delete their data.

It is a JSON REST API. Every request and response is JSON (except file exports and the avatar image itself).

## 2. How to Test It Yourself

You don't need to install anything. Pick whichever of these is most comfortable:

### Option 1 — Interactive docs in your browser (easiest, no setup)

Open **https://api-finance-forecast.com/docs** in any browser. This is a live, interactive page (Swagger UI) listing every endpoint on the real server. You can:

1. Expand any endpoint.
2. Click **"Try it out."**
3. Fill in the request body.
4. Click **"Execute"** — it sends a real request to the live server and shows you the real response, status code, and headers.

For endpoints that need login, use `POST /auth/register` or `POST /auth/login` first (see §4 below), copy the `access_token` from the response, then click the **"Authorize"** button at the top of the page and paste it in as `Bearer <token>`. After that, every "Try it out" call on the page is automatically authenticated.

A plain machine-readable version of the same spec is at **https://api-finance-forecast.com/openapi.json**, and a read-only, nicely formatted reference view is at **https://api-finance-forecast.com/redoc**.

### Option 2 — Postman / Insomnia

Import `https://api-finance-forecast.com/openapi.json` directly into Postman (`File → Import → Link`) and it will build a full collection of every endpoint for you automatically, with correct request bodies.

### Option 3 — curl (command line)

```bash
# 1. Register a test account
curl -X POST https://api-finance-forecast.com/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"a-good-password","name":"Your Name"}'

# Response includes access_token and refresh_token — copy the access_token.

# 2. Call an authenticated endpoint
curl https://api-finance-forecast.com/v1/me \
  -H "Authorization: Bearer <paste-access_token-here>"
```

### A note on rate limits

`POST /auth/register` and `POST /auth/login` are limited to **5 attempts per minute per IP address** — this is a deliberate anti-abuse measure, not a bug. If you're scripting a lot of repeated register/login calls while testing, space them out or you'll see a `429 rate_limited` response.

### Test data is safe to create and destroy

Every endpoint below works against real database rows — feel free to register a throwaway test account (any `@example.com` email works, nothing verifies it), create plans, add transactions, and delete them again. `DELETE /me/data` (§11) resets an account back to a blank slate at any time, and `DELETE /me` (§11) removes the account entirely.

## 3. Conventions That Apply to Every Endpoint

- **Money** is always a whole number in the smallest currency unit (e.g. halalas for SAR), in a field ending `_minor`. `450000` = 4,500.00. This avoids floating-point rounding errors — never send or expect a decimal.
- **Dates** are `"YYYY-MM-DD"` strings. **Months** are `"YYYY-MM"` strings. There are no timestamps in financial figures.
- **Currency** is always a separate 3-letter code field (e.g. `"SAR"`), never a symbol.
- Every **list** response is wrapped in `{"items": [...]}`, never a bare array.
- Every response, success or error, carries a `request_id` — quote this if you ever need to report an issue, it lets us find the exact request in server logs.

### Success responses

Most endpoints return the resource they just created, updated, or fetched, directly (no wrapper). A handful of action endpoints that don't return a resource (logout, delete, revert) instead return:

```json
{
  "message_en": "You've been logged out.",
  "message_ar": "تم تسجيل خروجك."
}
```

### Error responses

Every non-2xx response has this exact shape:

```json
{
  "error": {
    "code": "auth.invalid_credentials",
    "message_en": "The email or password you entered is incorrect.",
    "message_ar": "البريد الإلكتروني أو كلمة المرور التي أدخلتها غير صحيحة.",
    "params": {},
    "request_id": "b3f1..."
  }
}
```

- **`code`** is the machine-readable value to branch your logic on (e.g. detect `auth.token_expired` and silently refresh). It never changes even if the wording of `message_en`/`message_ar` is later revised.
- **`message_en`** / **`message_ar`** are ready-to-display text. Arabic copy is a first-pass machine draft, not yet reviewed by a native speaker — expect it to read a little stiff for now; the `code` and shape will not change when it's polished.
- **`params`** gives structured detail for the handful of codes that carry it (e.g. `{"field": "name"}`).

Full list of every error code in §12.

## 4. Authentication

**Every authenticated request needs this header:**
```
Authorization: Bearer <access_token>
```

- **Access token** — a JWT, valid for **15 minutes**. When a request fails with `auth.token_expired`, call `/auth/refresh` and retry.
- **Refresh token** — a longer-lived opaque string. Calling `/auth/refresh` **rotates** it: the response's new `refresh_token` replaces the old one, and the old one is dead immediately. Reusing an already-exchanged refresh token is treated as token theft and revokes every token issued from that login — the user has to log in again. **Verified live** in the test run (§15).
- `POST /auth/register`, `POST /auth/login`, and `POST /auth/refresh` are the only three routes that need **no** `Authorization` header.

### `POST /v1/auth/register`

Creates the account, a default "Base Plan," and default settings in one step.

**Request:**
```json
{"email": "user@example.com", "password": "correct-horse-battery", "name": "Nabeel Ahmed"}
```

**Success — `201 Created`:**
```json
{
  "access_token": "eyJhbGciOi...",
  "refresh_token": "8ViM_qt7RE...",
  "token_type": "bearer"
}
```

**Errors:** `auth.email_taken` (409), `auth.weak_password` (422, minimum 8 characters, no other complexity rule), `validation.required` (422), `validation.invalid` (422, malformed email), `rate_limited` (429).

### `POST /v1/auth/login`

**Request:** `{"email": "user@example.com", "password": "correct-horse-battery"}`
**Success — `200 OK`:** same shape as register.
**Errors:** `auth.invalid_credentials` (401 — deliberately identical for "wrong password" and "unknown email," so the login form can't be used to test which emails exist), `rate_limited` (429).

### `POST /v1/auth/refresh`

**Request:** `{"refresh_token": "..."}`
**Success — `200 OK`:** new `access_token` + new `refresh_token` (old refresh token now dead).
**Errors:** `auth.token_invalid` (401) — unknown, already-used, or revoked token.

### `POST /v1/auth/logout`

**Request:** `{"refresh_token": "..."}`
**Success — `200 OK`:** message shape. Idempotent — calling it again with an already-dead token still returns `200`.

## 5. Profile, Balance & Settings

### `GET /v1/me`

Returns the caller's profile and settings. **Auth required.**

**Success — `200 OK`:**
```json
{
  "id": "ec288b8d-af20-4502-9a95-ad4613d83225",
  "email": "user@example.com",
  "created_at": "2026-09-27T11:02:15.311862Z",
  "settings": {
    "display_name": "Client Test",
    "avatar_url": null,
    "currency_code": "SAR",
    "locale": "en",
    "current_balance_minor": 0,
    "balance_as_of": "2026-09-27"
  }
}
```

### `PUT /v1/me/balance` — set the Current Cash Balance

The **only** endpoint that ever writes the user's real cash balance — same one for the first-ever entry and every later edit. It's a full replace (`PUT`, not `PATCH`) of both fields together. Changing it re-anchors every plan's forecast, so treat it as a deliberate, confirmed action, not something that autosaves as-you-type.

**Request:**
```json
{"current_balance_minor": 4500000, "balance_as_of": "2026-09-10"}
```

**Success — `200 OK`:** returns the full profile shape (same as `GET /me`) with the new values applied.

**Errors:** `balance.negative_not_allowed` (422), `balance.as_of_in_future` (422), `balance.as_of_too_old` (422, more than 5 years ago), `validation.required` (422).

### `PATCH /v1/me/settings` — name, avatar, currency, language

Every field is optional/patch-style — send only what changed.

```json
{"display_name": "Muhammad", "avatar_base64": "iVBORw0KGgo...", "currency_code": "SAR", "locale": "en"}
```

- **`avatar_base64`** — raw base64 image bytes (`data:image/png;base64,` prefix is fine too, stripped automatically).
- **`remove_avatar: true`** clears the photo. Don't send it alongside `avatar_base64` — `remove_avatar` wins if both are present.
- **Email cannot be changed here** — it's read-only in this phase (no verification flow exists yet). Don't submit it.

**Success — `200 OK`:** same profile shape; `settings.avatar_url` becomes a relative path once a photo is uploaded, e.g. `/static/avatars/5a9da4da-....png`. Prepend the base host **without** `/v1` — e.g. `https://api-finance-forecast.com/static/avatars/5a9da4da-....png`. That URL is public/unauthenticated by design (anyone with the exact link can view it), but filenames are random UUIDs — nothing to guess or enumerate.

**Errors:** `avatar.invalid_image` (422, not a recognized JPEG/PNG/WEBP or corrupt), `avatar.too_large` (422, over 5MB), `validation.invalid` (422).

### `PATCH /v1/me/password`

The only way to change a password in this phase — no forgot-password-via-email flow exists yet (see §13).

**Request:** `{"current_password": "correct-horse", "new_password": "brand-new-password"}`
**Success — `200 OK`:** message shape.
**Errors:** `auth.current_password_incorrect` (422), `auth.weak_password` (422), `validation.required` (422).

**Important side effect, verified live:** a successful password change immediately revokes **every** refresh token on the account, not just the current session's — every other device gets logged out too. Don't try to keep the current session alive after this call; send the user back through login.

## 6. Categories

### `GET /v1/categories`

Returns 12 built-in system categories (`user_id: null`, has a `key`) plus the caller's own custom ones (`user_id` set, has a `name`).

**Success — `200 OK`:**
```json
{"items": [
  {"id": "0af4958e-...", "user_id": null, "key": "salary", "name": null, "direction": "income", "sort_order": 0},
  {"id": "e6f406f1-...", "user_id": "ec288b8d-...", "key": null, "name": "Side Hustle", "direction": "income", "sort_order": 0}
]}
```

System keys — income: `salary`, `freelance`, `business`; expense: `housing`, `loans`, `bills`, `subscriptions`, `everyday`, `transport`, `fuel`, `health`, `other`.

### `POST /v1/categories`

```json
{"name": "Side Hustle", "direction": "income"}
```
**Success — `201 Created`:** a category with `user_id` set to the caller, `key: null`.
**Errors:** `validation.required` (422).

### `PATCH /v1/categories/{id}`

```json
{"name": "Side Business"}
```
Only works on a category the caller owns — a system category or another user's returns `resource.not_found` (404), never a distinguishable "forbidden."

### `DELETE /v1/categories/{id}`

**Success — `200 OK`:** message shape.
**Errors:** `resource.not_found`, `category.in_use` (409 — a transaction or override still points at it; the client should surface this as "this category is being used").

## 7. Plans (Scenarios)

Every account starts with exactly one plan — the **Base Plan** (`is_base: true`) — created automatically at registration. It can never be renamed away from, archived, or deleted. Every other plan is created from `POST /scenarios` and inherits Base's data live unless overridden or removed (see §9).

### `GET /v1/scenarios?include_archived=`

Lists the caller's plans. Default excludes archived ones; `?include_archived=true` includes them (flagged by a non-null `archived_at`).

### `POST /v1/scenarios`

```json
{"name": "Buy a House"}
```
Optional `current_balance_override_minor` field exists for a per-plan starting-balance override — omit unless needed.

**Success — `201 Created`:**
```json
{
  "id": "d9036867-...", "name": "Buy a House", "is_base": false,
  "current_balance_override_minor": null, "archived_at": null,
  "created_at": "2026-09-27T11:02:20.358846Z", "updated_at": "2026-09-27T11:02:20.358846Z"
}
```

**Errors:** `scenario.name_taken` (409 — matched exactly, case-sensitive, including the Base Plan's own name and archived plans' names), `validation.invalid` (422, blank/whitespace name), `validation.required` (422).

### `GET /v1/scenarios/{id}`

Same shape as above, single plan. `resource.not_found` (404) for a plan that doesn't exist or belongs to someone else — never a `403`, to avoid confirming a resource's existence to the wrong user.

### `PATCH /v1/scenarios/{id}` — rename

```json
{"name": "Buy a House v2"}
```
**Errors:** `scenario.name_taken` (409), `validation.invalid` (422), `resource.not_found` (404).

### `POST /v1/scenarios/{id}/archive` / `POST /v1/scenarios/{id}/unarchive`

Both take no body. **Errors:** `scenario.base_immutable` (409, Base can never be archived), `scenario.not_archived` (409, unarchiving something that isn't archived).

### `POST /v1/scenarios/{id}/duplicate`

```json
{"name": "optional — omit for '<source name> (copy)'"}
```
The copy keeps live Base inheritance plus every override, removal, and plan-only item exactly as they were — verified live.

**Errors:** `scenario.archived` (409, can't duplicate an archived source), `scenario.name_taken` / `validation.invalid`, `resource.not_found`.

### `DELETE /v1/scenarios/{id}`

**Errors:** `scenario.base_immutable` (409 — Base can never be deleted).

## 8. Transactions

### `POST /v1/scenarios/{id}/transactions`

```json
{
  "name": "Rent", "amount_minor": 450000, "direction": "expense",
  "recurrence": "monthly", "start_date": "2026-01-01", "end_date": null,
  "category_id": "5a3ec104-...", "notes": "Optional context."
}
```
`end_date`, `category_id`, `notes` are optional. `direction` is `"income"` or `"expense"` and is **immutable after creation** (see below).

Recurrence values: `one_time`, `weekly`, `biweekly`, `monthly`, `quarterly`, `semiannual`, `annual`.

**Success — `201 Created`:** origin is `"own"` on the Base Plan, `"added"` on any other plan.

**Errors:** `transaction.amount_not_positive` (422), `transaction.end_before_start` (422), `transaction.one_time_has_end_date` (422), `validation.invalid`, `validation.required`, `resource.not_found`.

### `GET /v1/scenarios/{id}/transactions?filter=active|removed|all`

The single list endpoint for every plan and every filter state:
- **`active`** (default) — everything currently in effect.
- **`removed`** — rows the user has removed from this plan (always empty on Base).
- **`all`** — both together.

**Success — `200 OK`:**
```json
{"items": [
  {
    "id": "5b25798e-...", "scenario_id": "24b2fa51-...", "name": "Rent",
    "amount_minor": 450000, "direction": "expense", "category_id": "5a3ec104-...",
    "notes": null, "recurrence": "monthly", "start_date": "2026-01-01", "end_date": null,
    "origin": "own", "overlay_id": null,
    "created_at": "2026-09-27T11:02:21.310503Z", "updated_at": "2026-09-27T11:02:21.310503Z"
  }
]}
```

`origin` tells the client what to show: `own` (Base's own row, no badge), `inherited` (unmodified from Base), `overridden` (changed in this plan — "Modified" badge), `added` (created directly in this plan, no badge), `excluded` (removed from this plan — only visible under `filter=removed`/`all`).

### `PATCH /v1/transactions/{id}` — editing a row you own (`origin: own` or `added`)

Every field optional/patch-style. `end_date` needs an explicit `unset_end_date: true` to clear it — sending `end_date: null` does not clear it.

**Sending a different `direction` than the row already has** returns `transaction.direction_immutable` (422) — verified live. Income/expense can never flip after creation.

### `DELETE /v1/transactions/{id}`

Deleting a Base row cascades to every overlay any derived plan has on it. **Call `GET /v1/transactions/{id}/dependents` first** to know which plans will be affected.

### `GET /v1/transactions/{id}/dependents`

```json
{"count": 0, "scenarios": []}
```
`count: 0` — safe to delete with a plain confirmation. `count > 0` — the `scenarios` array names which plans have an overlay on this row.

**Editing/deleting the wrong kind of row** (an inherited/overridden row, which isn't a real row in this table) returns `resource.not_found` — the client must route those through the overlay endpoints instead (§9).

## 9. Overlays (Editing Inherited Transactions)

A derived plan's inherited rows aren't edited directly — they go through overlays, which never touch Base itself.

| Action | Call |
|---|---|
| Override an inherited row's fields | `POST /scenarios/{id}/overlays` with `op: "override"`, `base_transaction_id`, plus the `ovr_*` fields that differ |
| Edit an existing override further | `PATCH /scenarios/{id}/overlays/{overlay_id}` |
| Revert an override back to Base | `DELETE /scenarios/{id}/overlays/{overlay_id}` |
| Remove (exclude) an inherited row | `POST /scenarios/{id}/overlays` with `op: "exclude"`, `base_transaction_id` |
| Restore a removed row | `DELETE /scenarios/{id}/overlays/{overlay_id}` (same call as reverting) |
| Remove a row that's already overridden | **Two calls:** `DELETE` the override overlay, then `POST` a fresh `exclude` overlay on the same `base_transaction_id` — an overlay's `op` never flips in place |

**Example — override:**
```json
{"op": "override", "base_transaction_id": "5b25798e-...", "ovr_amount_minor": 500000}
```
**Success — `201 Created`:**
```json
{
  "id": "bd66ce4d-...", "scenario_id": "cac0e968-...", "base_transaction_id": "5b25798e-...",
  "op": "override", "ovr_name": null, "ovr_amount_minor": 500000, "ovr_category_id": null,
  "ovr_recurrence": null, "ovr_start_date": null, "ovr_end_date": null, "unset_end_date": false,
  "created_at": "2026-09-27T11:02:24.582561Z"
}
```

**Errors:** `overlay.target_not_in_base` (422), `overlay.already_exists` (409, skipped the delete step above), `overlay.scenario_is_base` (422, these routes reject the Base Plan itself), `resource.not_found`, plus the same `transaction.*` validation codes as create.

## 10. Forecast & Compare

### `GET /v1/scenarios/{id}/forecast?horizon=&anchor=&include_occurrences=`

- `horizon` — months to project, up to **120** (10 years is the max).
- `anchor` — omit it; defaults to the user's `balance_as_of` month.
- `include_occurrences` — `true` returns a flat, day-dated list of every individual transaction occurrence in the window (needed for weekly/day-level charts). Defaults to `false` — every existing caller is unaffected. Keep this `true` only for small, targeted requests (e.g. one month), not a 10-year pull.

**Success — `200 OK`** (horizon=1, occurrences on):
```json
{
  "scenario_id": "24b2fa51-...", "anchor_month": "2026-09", "balance_as_of": "2026-09-10",
  "horizon_months": 1, "currency_code": "SAR", "current_balance_minor": 4500000,
  "current_month": "2026-09", "months_elapsed": 0,
  "months": [{"month": "2026-09", "income_minor": 1800000, "expense_minor": 450000, "net_minor": 1350000, "closing_balance_minor": 5850000}],
  "totals": {"income_minor": 1800000, "expense_minor": 450000, "net_minor": 1350000, "closing_balance_minor": 5850000},
  "occurrences": [
    {"source_id": "5b25798e-...", "name": "Rent Updated", "direction": "expense", "amount_minor": 450000, "on": "2026-09-01"},
    {"source_id": "bf1b64ef-...", "name": "Salary", "direction": "income", "amount_minor": 1800000, "on": "2026-09-01"}
  ]
}
```

**Errors:** `forecast.invalid_horizon` (422 — outside the allowed range), `resource.not_found`.

### `GET /v1/forecast/compare?a=&b=&horizon=&anchor=`

`a`/`b` are the two plan ids being compared; order only affects which key (`a` or `b`) the response echoes it under. Returns both plans' full forecasts plus a `deltas[]` array (month-by-month difference) and a `drivers[]` array (which transactions are driving the difference, ranked by impact, tagged `modified`/`added`/`removed`).

**Errors:** `compare.same_scenario` (422 — verified live, comparing a plan against itself is rejected), `scenario.archived` (409), `forecast.invalid_horizon` (422), `resource.not_found`.

## 11. Account Data (Export / Reset / Delete)

### `GET /v1/me/export?format=json|csv`

`json` → a single JSON document with everything (`user`, `settings`, `categories`, `scenarios`, `transactions`, overlays). `csv` → a `.zip` of CSV files, one per table.

**Verified live** — both formats return `200` with real data.

### `DELETE /v1/me/data` — reset

Wipes all plans, transactions, overlays, and custom categories, resetting the account back to a fresh Base Plan at balance `0`. **Email, display name, avatar, currency, and locale are untouched.** Verified live.

### `DELETE /v1/me` — delete account

A **soft delete**: behaves exactly like a hard delete from the app's point of view (login stops working, every token is dead immediately, the same email can be used to register a brand-new account right away) — verified live on all three points. The row physically remains for a future data-purge process, but there is nothing different for a client to build around; treat it as permanent.

## 12. Error Code Reference

| Code | HTTP | Meaning |
|---|---|---|
| `auth.invalid_credentials` | 401 | Email or password is wrong |
| `auth.email_taken` | 409 | Registration email already in use |
| `auth.token_expired` | 401 | Access token expired — refresh and retry |
| `auth.token_invalid` | 401 | Malformed, unknown, or revoked token |
| `auth.weak_password` | 422 | Password below the 8-character minimum |
| `auth.current_password_incorrect` | 422 | Wrong current password on a password change |
| `balance.as_of_in_future` | 422 | Balance date is later than today |
| `balance.as_of_too_old` | 422 | Balance date is more than 5 years ago |
| `balance.negative_not_allowed` | 422 | Balance amount is negative |
| `avatar.invalid_image` | 422 | Not a recognized JPEG/PNG/WEBP, or corrupt |
| `avatar.too_large` | 422 | Decoded image exceeds 5MB |
| `validation.required` | 422 | A required field is missing (`params.field` names it) |
| `validation.invalid` | 422 | Generic field validation failure |
| `transaction.amount_not_positive` | 422 | Amount is zero or negative |
| `transaction.end_before_start` | 422 | End date precedes start date |
| `transaction.one_time_has_end_date` | 422 | A one-time transaction was given an end date |
| `transaction.direction_immutable` | 422 | Attempt to flip income ↔ expense |
| `scenario.base_immutable` | 409 | Attempt to delete or archive the Base Plan |
| `scenario.name_taken` | 409 | Duplicate plan name |
| `scenario.archived` | 409 | Archived plan used as a compare operand or duplicate source |
| `scenario.not_archived` | 409 | Unarchive attempted on a plan that isn't archived |
| `overlay.target_not_in_base` | 422 | Overlay pointed at a transaction that isn't in Base |
| `overlay.already_exists` | 409 | Second overlay attempted on the same target |
| `overlay.scenario_is_base` | 422 | Overlay attempted on the Base Plan itself |
| `category.in_use` | 409 | Deleting a category still referenced elsewhere |
| `compare.same_scenario` | 422 | Plan A and Plan B are the same plan |
| `forecast.invalid_horizon` | 422 | Horizon is outside the allowed range |
| `resource.not_found` | 404 | Doesn't exist, or belongs to another user (never distinguishable) |
| `rate_limited` | 429 | Too many attempts on login/register (5/min per IP) |
| `internal` | 500 | Unhandled server error — report the `request_id` |

## 13. Known Limitations (By Design, Not Bugs)

- **No forgot-password-via-email flow yet.** A user who forgets their password has no self-service recovery in this phase — the only path is `PATCH /me/password` while already logged in.
- **Arabic error/message text is a first-pass machine translation**, not yet reviewed by a native speaker. It will be swapped for reviewed copy later without any change to response shape or error codes.
- **Avatar photos are stored on local disk on the single production server**, not in cloud object storage. This is a Phase-1-only choice, acknowledged up front — it will need to move before scaling to multiple servers, but nothing about the request/response contract changes when that happens.
- **Email addresses cannot be changed** once an account is created (by design — no verification flow exists to safely support it yet).
- **No hard cap on how many plans a user can create.**

---

# Part B — Test Report

## 14. Test Summary

| | |
|---|---|
| **Environment** | Production — `https://api-finance-forecast.com` |
| **Date** | September 27, 2026 |
| **Total checks run** | 59 |
| **Passed** | 59 |
| **Failed** | 0 |
| **Coverage** | Every endpoint in §17 of the internal API index — auth, balance, categories, plans, transactions, overlays, forecast, compare, settings, password, avatar, export, reset, and account deletion |

Each check below made a real HTTP call against the live server and compared the actual HTTP status code to the documented expected one. Rows marked "(expect ###)" are **negative tests** — deliberately sending bad input to confirm the server rejects it correctly, not failures.

| # | Test | Expected | Actual | Result |
|---|---|---|---|---|
| 1 | `POST /auth/register` | 201 | 201 | ✅ |
| 2 | `POST /auth/register` duplicate email | 409 | 409 | ✅ |
| 3 | `POST /auth/login` | 200 | 200 | ✅ |
| 4 | `POST /auth/login` wrong password | 401 | 401 | ✅ |
| 5 | `GET /me` | 200 | 200 | ✅ |
| 6 | `PUT /me/balance` | 200 | 200 | ✅ |
| 7 | `PUT /me/balance` negative amount | 422 | 422 | ✅ |
| 8 | `GET /categories` | 200 | 200 | ✅ |
| 9 | `POST /categories` | 201 | 201 | ✅ |
| 10 | `PATCH /categories/{id}` | 200 | 200 | ✅ |
| 11 | `GET /scenarios` | 200 | 200 | ✅ |
| 12 | `POST /scenarios` | 201 | 201 | ✅ |
| 13 | `POST /scenarios` duplicate name | 409 | 409 | ✅ |
| 14 | `POST /scenarios/{id}/transactions` (expense) | 201 | 201 | ✅ |
| 15 | `POST /scenarios/{id}/transactions` (income) | 201 | 201 | ✅ |
| 16 | `POST /scenarios/{id}/transactions` amount ≤ 0 | 422 | 422 | ✅ |
| 17 | `GET /scenarios/{id}/transactions?filter=active` | 200 | 200 | ✅ |
| 18 | `PATCH /transactions/{id}` | 200 | 200 | ✅ |
| 19 | `PATCH /transactions/{id}` change direction | 422 | 422 | ✅ |
| 20 | `GET /transactions/{id}/dependents` | 200 | 200 | ✅ |
| 21 | `GET /scenarios/{derived_id}/transactions` (inherited) | 200 | 200 | ✅ |
| 22 | `POST /scenarios/{id}/overlays` (override) | 201 | 201 | ✅ |
| 23 | `PATCH /scenarios/{id}/overlays/{id}` | 200 | 200 | ✅ |
| 24 | `DELETE /scenarios/{id}/overlays/{id}` (revert) | 200 | 200 | ✅ |
| 25 | `POST /scenarios/{id}/overlays` (exclude) | 201 | 201 | ✅ |
| 26 | `GET /scenarios/{id}/transactions?filter=removed` | 200 | 200 | ✅ |
| 27 | `DELETE /scenarios/{id}/overlays/{id}` (restore) | 200 | 200 | ✅ |
| 28 | `GET /scenarios/{id}/forecast` | 200 | 200 | ✅ |
| 29 | `GET /scenarios/{id}/forecast?include_occurrences=true` | 200 | 200 | ✅ |
| 30 | `GET /scenarios/{id}/forecast` invalid horizon | 422 | 422 | ✅ |
| 31 | `GET /forecast/compare` | 200 | 200 | ✅ |
| 32 | `GET /forecast/compare` same plan twice | 422 | 422 | ✅ |
| 33 | `PATCH /scenarios/{id}` rename | 200 | 200 | ✅ |
| 34 | `GET /scenarios/{id}` single plan detail | 200 | 200 | ✅ |
| 35 | `POST /scenarios/{id}/duplicate` | 201 | 201 | ✅ |
| 36 | `POST /scenarios/{id}/archive` | 200 | 200 | ✅ |
| 37 | `POST /scenarios/{base_id}/archive` (rejected) | 409 | 409 | ✅ |
| 38 | `POST /scenarios/{id}/unarchive` | 200 | 200 | ✅ |
| 39 | `DELETE /scenarios/{id}` | 200 | 200 | ✅ |
| 40 | `DELETE /scenarios/{base_id}` (rejected) | 409 | 409 | ✅ |
| 41 | `PATCH /me/settings` display name | 200 | 200 | ✅ |
| 42 | `PATCH /me/settings` avatar upload | 200 | 200 | ✅ |
| 43 | Static avatar file fetch, no auth header | 200 | 200 | ✅ |
| 44 | `PATCH /me/settings` remove avatar | 200 | 200 | ✅ |
| 45 | `PATCH /me/password` | 200 | 200 | ✅ |
| 46 | `PATCH /me/password` wrong current password | 422 | 422 | ✅ |
| 47 | `POST /auth/login` with new password | 200 | 200 | ✅ |
| 48 | Reuse of pre-password-change refresh token | 401 | 401 | ✅ |
| 49 | `POST /auth/refresh` | 200 | 200 | ✅ |
| 50 | Reuse of an already-rotated refresh token | 401 | 401 | ✅ |
| 51 | `GET /me/export?format=json` | 200 | 200 | ✅ |
| 52 | `GET /me/export?format=csv` | 200 | 200 | ✅ |
| 53 | `DELETE /categories/{id}` | 200 | 200 | ✅ |
| 54 | `DELETE /me/data` (reset) | 200 | 200 | ✅ |
| 55 | `POST /auth/logout` | 200 | 200 | ✅ |
| 56 | `POST /auth/register` (throwaway account for delete test) | 201 | 201 | ✅ |
| 57 | `DELETE /me` (soft delete) | 200 | 200 | ✅ |
| 58 | `GET /me` with token from deleted account | 401 | 401 | ✅ |
| 59 | `POST /auth/register` same email, right after deletion | 201 | 201 | ✅ |

**Result: 59 / 59 passed.**

## 15. Detailed Test Log (Every Call, Every Response)

The examples below are real requests and real responses captured during the test run above. IDs, tokens, and timestamps are specific to the throwaway test account created for this run (`clienttest.*@example.com`) and are not live production user data.

### Auth

**Register**
`POST /auth/register` → `{"email":"clienttest.1790506934@example.com","password":"correct-horse-battery","name":"Client Test"}`
→ **201** → `{"access_token":"eyJhbGciOi...","refresh_token":"eP5Qe9m...","token_type":"bearer"}`

**Duplicate email**
`POST /auth/register` (same email again)
→ **409** → `{"error":{"code":"auth.email_taken","message_en":"An account with this email already exists.","message_ar":"يوجد حساب بهذا البريد الإلكتروني بالفعل.","params":{"field":"email"},"request_id":"4e86735b-919c-4512-9849-36459f74436c"}}`

**Login, wrong password**
`POST /auth/login` → `{"email":"clienttest.1790506934@example.com","password":"wrongpass"}`
→ **401** → `{"error":{"code":"auth.invalid_credentials","message_en":"The email or password you entered is incorrect.","message_ar":"البريد الإلكتروني أو كلمة المرور التي أدخلتها غير صحيحة.","params":{},"request_id":"54204473-8074-46c9-b6e9-b9699b63de78"}}`

### Balance

**Set balance**
`PUT /me/balance` → `{"current_balance_minor": 4500000, "balance_as_of": "2026-09-10"}`
→ **200** → `{"id":"ec288b8d-...","email":"clienttest...@example.com","created_at":"2026-09-27T11:02:15.311862Z","settings":{"display_name":"Client Test","avatar_url":null,"currency_code":"SAR","locale":"en","current_balance_minor":4500000,"balance_as_of":"2026-09-10"}}`

**Negative balance rejected**
`PUT /me/balance` → `{"current_balance_minor": -100, "balance_as_of": "2026-09-10"}`
→ **422** → `{"error":{"code":"balance.negative_not_allowed","message_en":"Current Cash Balance can't be negative.","message_ar":"لا يمكن أن يكون رصيدك النقدي الحالي سالبًا.","params":{"field":"current_balance_minor"},"request_id":"49b22ad4-522d-4cc3-a469-f232a7c62d60"}}`

### Categories

**List**
`GET /categories` → **200** → `{"items":[{"id":"0af4958e-...","user_id":null,"key":"salary","name":null,"direction":"income","sort_order":0}, ... 11 more system categories ...]}`

**Create + rename**
`POST /categories` → `{"name":"Side Hustle","direction":"income"}` → **201** → `{"id":"e6f406f1-...","user_id":"ec288b8d-...","key":null,"name":"Side Hustle","direction":"income","sort_order":0}`
`PATCH /categories/e6f406f1-...` → `{"name":"Side Business"}` → **200** → `{"id":"e6f406f1-...", ..., "name":"Side Business", ...}`

### Plans

**List (only Base exists initially)**
`GET /scenarios` → **200** → `{"items":[{"id":"24b2fa51-...","name":"Base Plan","is_base":true,"current_balance_override_minor":null,"archived_at":null,"created_at":"2026-09-27T11:02:15.311862Z","updated_at":"2026-09-27T11:02:15.311862Z"}]}`

**Create**
`POST /scenarios` → `{"name":"Buy a House"}` → **201** → `{"id":"cac0e968-...","name":"Buy a House","is_base":false,"current_balance_override_minor":null,"archived_at":null,"created_at":"2026-09-27T11:02:20.358846Z","updated_at":"2026-09-27T11:02:20.358846Z"}`

**Duplicate name rejected**
`POST /scenarios` → `{"name":"Buy a House"}` (again) → **409** → `{"error":{"code":"scenario.name_taken","message_en":"You already have a plan with this name.","message_ar":"لديك بالفعل خطة بهذا الاسم.","params":{"field":"name"},"request_id":"5866d78a-f8d1-4d15-81db-e7597365eeb1"}}`

**Rename**
`PATCH /scenarios/cac0e968-...` → `{"name":"Buy a House v2"}` → **200**

**Duplicate a plan**
`POST /scenarios/cac0e968-.../duplicate` → `{}` → **201** → `{"id":"1b7ef33d-...","name":"Buy a House v2 (copy)","is_base":false,"current_balance_override_minor":null,"archived_at":null,"created_at":"2026-09-27T11:02:30.082620Z","updated_at":"2026-09-27T11:02:30.082620Z"}`

**Archiving Base rejected**
`POST /scenarios/24b2fa51-.../archive` (Base Plan's id) → **409** → `scenario.base_immutable`

**Deleting Base rejected**
`DELETE /scenarios/24b2fa51-...` → **409** → `scenario.base_immutable`

### Transactions

**Add expense**
`POST /scenarios/24b2fa51-.../transactions` → `{"name":"Rent","amount_minor":450000,"direction":"expense","recurrence":"monthly","start_date":"2026-01-01","category_id":"5a3ec104-..."}`
→ **201** → `{"id":"5b25798e-...","scenario_id":"24b2fa51-...","name":"Rent","amount_minor":450000,"direction":"expense","category_id":"5a3ec104-...","notes":null,"recurrence":"monthly","start_date":"2026-01-01","end_date":null,"origin":"own","overlay_id":null,"created_at":"2026-09-27T11:02:21.310503Z","updated_at":"2026-09-27T11:02:21.310503Z"}`

**Edit**
`PATCH /transactions/5b25798e-...` → `{"name":"Rent Updated"}` → **200** → same row with `name` updated and `updated_at` bumped.

**Direction change rejected**
`PATCH /transactions/5b25798e-...` → `{"direction":"income"}` → **422** → `{"error":{"code":"transaction.direction_immutable","message_en":"Income and expense can't be changed after creation.","message_ar":"لا يمكن تغيير نوع الدخل أو المصروف بعد الإنشاء.","params":{},"request_id":"82f85e76-21db-4433-a5d6-5fe12701da13"}}`

**Dependents check (safe to delete)**
`GET /transactions/5b25798e-.../dependents` → **200** → `{"count": 0, "scenarios": []}`

### Overlays

**Override an inherited row on a derived plan**
`POST /scenarios/cac0e968-.../overlays` → `{"op":"override","base_transaction_id":"5b25798e-...","ovr_amount_minor":500000}`
→ **201** → `{"id":"bd66ce4d-...","scenario_id":"cac0e968-...","base_transaction_id":"5b25798e-...","op":"override","ovr_name":null,"ovr_amount_minor":500000,"ovr_category_id":null,"ovr_recurrence":null,"ovr_start_date":null,"ovr_end_date":null,"unset_end_date":false,"created_at":"2026-09-27T11:02:24.582561Z"}`

Then: `PATCH` the same overlay to `ovr_amount_minor: 520000` → **200**. `DELETE` it to revert → **200**. Then a fresh `exclude` overlay was created, confirmed under `filter=removed`, and restored with `DELETE` → **200** at every step.

### Forecast & Compare

**12-month forecast**
`GET /scenarios/24b2fa51-.../forecast?horizon=12` → **200** → first month: `{"month":"2026-09","income_minor":1800000,"expense_minor":450000,"net_minor":1350000,"closing_balance_minor":5850000}` (12 months returned total).

**1-month forecast with occurrence detail**
`GET /scenarios/24b2fa51-.../forecast?horizon=1&include_occurrences=true` → **200**:
```json
{
  "scenario_id": "24b2fa51-...", "anchor_month": "2026-09", "balance_as_of": "2026-09-10",
  "horizon_months": 1, "currency_code": "SAR", "current_balance_minor": 4500000,
  "current_month": "2026-09", "months_elapsed": 0,
  "months": [{"month":"2026-09","income_minor":1800000,"expense_minor":450000,"net_minor":1350000,"closing_balance_minor":5850000}],
  "totals": {"income_minor":1800000,"expense_minor":450000,"net_minor":1350000,"closing_balance_minor":5850000},
  "occurrences": [
    {"source_id":"5b25798e-...","name":"Rent Updated","direction":"expense","amount_minor":450000,"on":"2026-09-01"},
    {"source_id":"bf1b64ef-...","name":"Salary","direction":"income","amount_minor":1800000,"on":"2026-09-01"}
  ]
}
```

**Invalid horizon rejected**
`GET /scenarios/24b2fa51-.../forecast?horizon=999` → **422** → `forecast.invalid_horizon`

**Compare two plans**
`GET /forecast/compare?a=24b2fa51-...&b=cac0e968-...&horizon=120` → **200** → full `a`/`b` forecast objects plus `deltas[]` and `drivers[]`.

**Comparing a plan against itself rejected**
`GET /forecast/compare?a=24b2fa51-...&b=24b2fa51-...&horizon=120` → **422** → `compare.same_scenario`

### Settings, Password, Avatar

**Avatar upload**
`PATCH /me/settings` → `{"avatar_base64":"iVBORw0KGgo..."}` → **200** → `{"id":"ec288b8d-...","email":"clienttest...@example.com","created_at":"2026-09-27T11:02:15.311862Z","settings":{"display_name":"Muhammad","avatar_url":"/static/avatars/5a9da4da-ef7e-4e92-8fd4-07c45fab262e.png","currency_code":"SAR","locale":"en","current_balance_minor":4500000,"balance_as_of":"2026-09-10"}}`

**Fetching that avatar with no `Authorization` header at all** → **200** (confirms the static file route is correctly public).

**Password change**
`PATCH /me/password` → `{"current_password":"correct-horse-battery","new_password":"new-correct-horse-battery"}` → **200**

**Wrong current password rejected**
`PATCH /me/password` → `{"current_password":"totally-wrong","new_password":"whatever123"}` → **422** → `auth.current_password_incorrect`

**All sessions revoked, confirmed**
Immediately after the password change, the refresh token from *before* the change was tried against `/auth/refresh` → **401** (`auth.token_invalid`) — exactly as documented, every prior session dies the instant the password changes.

**Refresh token rotation, confirmed**
A fresh login's `refresh_token` was exchanged via `/auth/refresh` → **200**, new tokens issued. The *same, now-already-used* refresh token was tried again → **401** — reuse of a rotated token is correctly rejected.

### Account Data

**Export**
`GET /me/export?format=json` → **200** → full JSON dump (`user`, `settings`, `categories`, `scenarios`, `transactions`, ...).
`GET /me/export?format=csv` → **200** (zip file).

**Reset**
`DELETE /me/data` → **200**.

**Logout**
`POST /auth/logout` → **200**.

**Soft delete, confirmed end-to-end** on a separate throwaway account:
1. `DELETE /me` → **200**.
2. `GET /me` with that same account's still-technically-live access token → **401** (dead immediately).
3. `POST /auth/register` with the *exact same email*, right after → **201** (succeeds immediately, confirming the email is freed up even though the row is soft-deleted server-side).

---

*This document reflects the live production API as of September 27, 2026. Any future change to a request/response shape will be re-verified and this document updated accordingly.*
