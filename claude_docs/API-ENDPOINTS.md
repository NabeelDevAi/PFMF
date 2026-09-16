# Horizon — API Reference (Flutter Integration)

This is the handoff document for Flutter development. It is a **living document**: as each Figma screen is verified against the backend (screen-by-screen, feature by feature), the endpoint(s) it depends on get their full contract written up here — exact request/response shapes, real examples, every error the client needs to handle. Nothing goes in here as a guess; every entry below was hit with a real HTTP request against the running backend before being written down.

For the full endpoint index (every endpoint that exists, whether or not it's been screen-verified yet), see `backend-plan/08-api-endpoints-plan.md` — that's the internal planning doc. This file is the subset of it that's actually been walked through screen-by-screen, in the detail a client needs to integrate against it.

**Status legend:**
- ✅ **Verified** — walked through against a specific Figma screen, contract below is exact and tested.
- ⏳ **Not yet verified** — endpoint exists and is fully tested server-side, but hasn't been matched against its Figma screen yet. Listed in the index (§14) so nothing is forgotten; full contract lands here once its turn comes.

---

## 1. Base URL

No production/staging URL yet — deployment is explicitly not scheduled for this phase. For local development against the backend running on your machine:

| Client | Base URL |
|---|---|
| Android emulator | `http://10.0.2.2:8000/v1` |
| iOS simulator | `http://127.0.0.1:8000/v1` |
| Physical device (same Wi-Fi as the dev machine) | `http://<dev-machine-LAN-IP>:8000/v1` |

Every path below is written **relative to that base** (e.g. `/auth/login` means `http://10.0.2.2:8000/v1/auth/login`). The server is started with `uvicorn app.main:app --reload` from `backend/`, default port `8000`.

Mobile-only (confirmed) — CORS is a browser-only restriction and does not apply to native Android/iOS HTTP calls, so it's a non-issue here.

---

## 2. Auth

**Header for every authenticated request:**
```
Authorization: Bearer <access_token>
```

- **Access token**: JWT, expires in **15 minutes**. When a request fails with `auth.token_expired`, call `/auth/refresh` and retry.
- **Refresh token**: opaque string, longer-lived. Every call to `/auth/refresh` **rotates** it — the response's new `refresh_token` replaces the old one in client storage; the old one stops working immediately. **Never reuse a refresh token you've already exchanged** — doing so is treated as token theft and revokes every token issued from that login (the user is forced to log in again).
- Routes that need **no** `Authorization` header at all: `POST /auth/register`, `POST /auth/login`, `POST /auth/refresh`.

---

## 3. Response conventions (apply to every endpoint below)

- **Money** is always a plain integer in minor units (e.g. halalas), in a field named `..._minor`. Never a decimal, never a formatted string. Format it client-side.
- **Dates** are `"YYYY-MM-DD"` strings; **months** are `"YYYY-MM"` strings. No timestamps anywhere in financial data.
- **Currency** is always a separate ISO code field (e.g. `"SAR"`), never a symbol.
- Every **list** response is wrapped in an `"items"` array field, not returned as a bare JSON array.
- Every response (success or error) carries a `request_id` — useful for bug reports, not meant to be shown to the user.

### 3.1 Error response shape

Every non-2xx response has this shape:

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

- **`code`** is machine-readable — branch on this (e.g. `auth.token_expired` → silently refresh and retry), never on `message_en`/`message_ar`.
- **`message_en`** / **`message_ar`** are ready-to-display text, generated server-side. Pick one by the phone's system language — no client-side translation table needed. **Caveat: the Arabic text is a first-pass machine draft, not yet reviewed by a native speaker** — expect it to be swapped for reviewed copy later; the `code` and the response shape itself will not change when that happens.
- **`params`** gives structured detail for the few codes that carry it (e.g. `{"field": "name"}` for a missing-field validation error) — not meant to be interpolated into the message text.

Full error code reference: §15 below.

### 3.2 Action-confirmation response shape

A handful of endpoints that don't return any resource (e.g. delete/logout) return `200 OK` with this shape instead of an empty body:

```json
{
  "message_en": "You've been logged out.",
  "message_ar": "تم تسجيل خروجك."
}
```

Every other endpoint returns the resource it just created/changed/fetched directly (no wrapper) — the client already has what it needs from that data.

---

## 4. Auth endpoints ✅ Verified

**Figma screens:** Sign Up, Login.

### `POST /auth/register`

Creates the account, its Base Plan, and default settings in one step. `name` is required — it's stored as the user's display name from the moment the account exists (never blank/null for a new user).

**Request:**
```json
{
  "email": "user@example.com",
  "password": "correct-horse-battery",
  "name": "Nabeel Ahmed"
}
```

**Success — `201 Created`:**
```json
{
  "access_token": "eyJhbGciOi...",
  "refresh_token": "8ViM_qt7RE...",
  "token_type": "bearer"
}
```

**Errors:**

| `code` | HTTP | When |
|---|---|---|
| `auth.email_taken` | 409 | Email already registered |
| `auth.weak_password` | 422 | Password fails policy (see below) |
| `validation.required` | 422 | `name`, `email`, or `password` missing — `params.field` names which one |
| `validation.invalid` | 422 | Malformed email |
| `rate_limited` | 429 | More than 5 attempts/minute from the same IP |

**Password policy:** minimum **8 characters**, no other complexity rule (no forced uppercase/digit/symbol). Same rule on register and on `PATCH /me/password`. Safe to mirror client-side for instant form feedback — the server is still the source of truth and returns `auth.weak_password` either way.

### `POST /auth/login`

**Request:**
```json
{
  "email": "user@example.com",
  "password": "correct-horse-battery"
}
```

**Success — `200 OK`:** same shape as register's success response (`access_token`, `refresh_token`, `token_type`).

**Errors:**

| `code` | HTTP | When |
|---|---|---|
| `auth.invalid_credentials` | 401 | Wrong password **or** unknown email — deliberately the same code/message for both, so a login form can never be used to test which emails are registered |
| `rate_limited` | 429 | More than 5 attempts/minute from the same IP |

### `POST /auth/refresh`

**Request:** `{"refresh_token": "..."}`
**Success — `200 OK`:** new `access_token` + new `refresh_token` (old refresh token is now dead).
**Errors:** `auth.token_invalid` (401) — unknown, already-used, or revoked token.

### `POST /auth/logout`

**Request:** `{"refresh_token": "..."}`
**Success — `200 OK`:** action-confirmation shape (§3.2). Idempotent — calling it with an already-invalid token still returns `200`, not an error.

---

## 5. Current Cash Balance ✅ Verified

**Figma screens:** Onboarding 2 (initial balance entry), Settings → Current Cash Balance / B3 (later edits).

### `PUT /me/balance`

**The only endpoint that ever writes the Current Cash Balance** — same one for the very first entry during onboarding and every later edit. There is no separate "set once" call; `PUT` (not `POST`) because it's a full replace of both fields together, not a partial patch. It always requires auth, so it's called *after* `POST /auth/register` has already returned a token pair — onboarding's balance step is not part of registration itself.

Changing it re-anchors every plan's forecast (the whole point of the Current Cash Balance being separate from any transaction), so the client should treat this as a deliberate, confirmed action, not something that saves as-you-type.

**Request:**
```json
{
  "current_balance_minor": 4500000,
  "balance_as_of": "2026-09-10"
}
```
(`4500000` = 45,000.00 in a 2-decimal currency like SAR — minor units, same convention as every other amount in the API.)

**Success — `200 OK`:** returns the full `MeOut` shape (same as `GET /me`), so the client can refresh its whole picture from one response:
```json
{
  "id": "ad9c60cb-...",
  "email": "user@example.com",
  "created_at": "2026-09-16T16:15:56.495134+05:00",
  "settings": {
    "display_name": "Nabeel Ahmed",
    "currency_code": "SAR",
    "locale": "en",
    "current_balance_minor": 4500000,
    "balance_as_of": "2026-09-10"
  }
}
```

**Errors:**

| `code` | HTTP | When |
|---|---|---|
| `balance.negative_not_allowed` | 422 | `current_balance_minor < 0` — zero is fine, negative (overdraft/debt) is rejected |
| `balance.as_of_in_future` | 422 | `balance_as_of` is later than today |
| `balance.as_of_too_old` | 422 | `balance_as_of` is more than **5 years** in the past |
| `validation.required` | 422 | Either field missing |
| `auth.token_invalid` / `auth.token_expired` | 401 | Missing/expired/invalid access token |

**Defaults at registration:** a brand-new account starts at `current_balance_minor: 0`, `balance_as_of: <today>` — set automatically by `POST /auth/register`, before the user ever calls this endpoint. So `GET /me` right after signup already returns valid (if placeholder) balance fields; the onboarding balance screen's job is to overwrite that placeholder with the user's real figure, not to create it from nothing.

**Numeric input note for the client:** since negative values are now rejected server-side, the amount field can safely be a plain non-negative numeric input (no minus-sign affordance needed).

---

## 6. Plan creation ✅ Verified

**Figma screen:** Create Plan (name only — no starting-balance override on this screen).

### `POST /scenarios`

Creates a new plan ("scenario" internally) for the caller. Every new account already has exactly one plan from registration — the **Base Plan** (`is_base: true`) — which cannot be created, renamed away from, deleted, or archived by this or any other endpoint; this call always creates a new, non-Base plan alongside it.

**Request** (this screen only ever sends `name`):
```json
{
  "name": "Buy a House"
}
```

The schema also accepts an optional `current_balance_override_minor` (a per-plan override of the Current Cash Balance) — **not used by this screen**, so omit it entirely; it's documented in full whenever the screen that actually sets it is verified.

**Success — `201 Created`:**
```json
{
  "id": "d9036867-8a86-41be-a3af-475b0cd2ff06",
  "name": "Buy a House",
  "is_base": false,
  "current_balance_override_minor": null,
  "archived_at": null,
  "created_at": "2026-09-16T16:34:56.804502+05:00",
  "updated_at": "2026-09-16T16:34:56.804502+05:00"
}
```

**Errors:**

| `code` | HTTP | When |
|---|---|---|
| `scenario.name_taken` | 409 | The caller already has a plan with this exact name — **including the Base Plan's own name ("Base Plan") and any archived plan's name.** Uniqueness is per-user across every plan regardless of archived state, not just active ones. |
| `validation.invalid` | 422 | Name is blank or whitespace-only after trimming (e.g. `""`, `"   "`) |
| `validation.required` | 422 | Name missing entirely |

**Name matching is exact and case-sensitive, with no trimming of the stored value.** `"Buy a House"` and `"buy a house"` are treated as different, non-conflicting names; a name with accidental leading/trailing spaces (e.g. `"  Buy a House  "`) is stored exactly as typed, not trimmed. Only a name that's *entirely* whitespace is rejected (see `validation.invalid` above) — trim on the client side before sending if you want to avoid the case-sensitivity/whitespace edge cases from ever reaching the user as a confusing "already taken" or "looks identical but isn't" situation.

---

## 7. Transactions list, badges, and remove/restore ✅ Verified

**Figma screens:** Transactions (all three variants — Base/derived plan, Expense/Income, and the filter behind the search bar's sliders icon).

### `GET /scenarios/{id}/transactions?filter=`

This is the **one and only** transactions-list endpoint, for every plan (Base or derived) and every filter state. There's no separate "removed items" endpoint.

**Query param `filter`** — `"active"` (default), `"removed"`, or `"all"`:
- **`active`** — everything currently in effect in this plan. This is what the "Active only" tab (and the plan screen's default load) should call. On the Base Plan this is simply every transaction it owns (`origin: "own"`). On a derived plan it's the inherited/overridden/added rows — never anything the user has removed.
- **`removed`** — only the rows the user has removed from this plan (`origin: "excluded"`). **Always empty on the Base Plan** — Base can't remove anything, removal only exists relative to Base. Feed this to the "Removed only" tab.
- **`all`** — active + removed together, in one call. Feed this to the "All" tab — no need to call twice and merge client-side.

Nothing else about the request changes — same path, same auth, no body.

**Response** (same `TransactionOut` shape regardless of `filter`):
```json
{
  "items": [
    {
      "id": "8f490ab2-8ec7-4286-9c4a-0f844eeec382",
      "scenario_id": "113c24b3-...",
      "name": "Rent",
      "amount_minor": 780000,
      "direction": "expense",
      "category_id": null,
      "notes": null,
      "recurrence": "monthly",
      "start_date": "2026-01-01",
      "end_date": null,
      "origin": "overridden",
      "overlay_id": "5dbd8431-5e0c-4266-85d9-0e5578bfc77c",
      "created_at": "2026-09-16T17:01:05.297554+05:00",
      "updated_at": "2026-09-16T17:01:05.297554+05:00"
    }
  ]
}
```

**`origin` is exactly what drives every badge in these three screens:**

| `origin` | Badge shown | Meaning |
|---|---|---|
| `own` | *(none)* | A Base Plan's own transaction — Base only ever has this origin |
| `inherited` | `From Base` | Unmodified, inherited from Base |
| `overridden` | `Modified` | A Base transaction, changed in this plan (amount/name/date/etc.) |
| `added` | *(none — it's just this plan's own row)* | Created directly in this (derived) plan, not from Base |
| `excluded` | *(shown only under `filter=removed`/`all`)* | Removed from this plan — the row still shows Base's original values, untouched |

**`overlay_id`** — present (non-null) only for `overridden` and `excluded` rows; always `null` for `own`/`inherited`/`added`. This is the id to call the overlay endpoints with:
- **Editing a `Modified` row further, or reverting it back to Base:** `PATCH`/`DELETE /scenarios/{id}/overlays/{overlay_id}`.
- **Restoring a removed row** (the "Undo" action in the Buy a House screenshot, or a "Restore" button in the Removed-only tab): `DELETE /scenarios/{id}/overlays/{overlay_id}` — same endpoint as reverting an override; the overlay disappears and the row goes back to being `inherited`.
- **A `Modified`/removed row's `overlay_id` is stable across reloads** — fetch it fresh from this same endpoint any time; don't rely on remembering the id from when the overlay was first created (`POST /scenarios/{id}/overlays`'s response also returns it, but that's only needed at the moment of creation).
- **Creating** the override/exclude in the first place still goes through `POST /scenarios/{id}/overlays` with `base_transaction_id` (an `inherited` row's own `id` field) — that part doesn't change; see `08-api-endpoints-plan.md`'s Overlays section for that endpoint's full request shape once it gets its own screen turn.

**Errors:**

| `code` | HTTP | When |
|---|---|---|
| `validation.invalid` | 422 | `filter` isn't one of `active`/`removed`/`all` |
| `resource.not_found` | 404 | Plan doesn't exist or belongs to another user |

---

## 8. Add / edit / delete a transaction ✅ Verified

**Figma screens:** New expense/income (amount-first entry), Edit transaction (own/Base row — Save changes, Delete), Edit transaction (category picker sheet), Edit transaction (schedule sheet), Edit transaction (Modified/overridden row — Save changes, Revert to Base, Remove from this plan).

The fields on every one of these screens (name, amount, category, schedule, notes, plus the income/expense entry toggle) map onto the same request bodies whether it's the create screen or the edit screen — there's no separate "quick add" vs. "full add" shape.

### 8.1 Create — `POST /scenarios/{id}/transactions`

```json
{
  "name": "Rent",
  "amount_minor": 450000,
  "direction": "expense",
  "recurrence": "monthly",
  "start_date": "2026-01-01",
  "end_date": null,
  "category_id": "2fa6e445-be55-4fee-9ab7-68b7869d6791",
  "notes": "Optional context for this transaction."
}
```
`end_date`, `category_id`, `notes` are all optional (omit or `null`). **Success — `201 Created`:** a `TransactionOut` (§7's shape — `origin` is `own` on the Base Plan, `added` on any other plan; `overlay_id` is always `null` here, since a freshly-created row never has an overlay).

**Errors:** `transaction.amount_not_positive` (422, `amount_minor <= 0`), `transaction.end_before_start` (422), `transaction.one_time_has_end_date` (422, a `one_time` recurrence can't carry an `end_date`), `validation.invalid` (422, e.g. a `category_id` that doesn't exist or isn't visible to this user), `validation.required`, `resource.not_found` (bad `scenario_id`).

### 8.2 Editing a row you own directly (`origin: "own"` or `"added"`) — the plain Edit screens (2 & 3 in your screenshots)

- **"Save changes"** → `PATCH /transactions/{id}`. Every field is optional/patch-style — send only what changed. Confirmed: name, `amount_minor`, `category_id`, `recurrence`, `notes` all update correctly; `end_date` has an explicit `unset_end_date: true` flag to clear it back to open-ended (sending `end_date: null` is not read as "clear it" — only `unset_end_date` is).
- **The Expense/Income toggle is correctly greyed out in your mockup — this matches real backend behavior.** `direction` is accepted in the request body only to detect a change and reject it: sending a different `direction` than the row already has returns `transaction.direction_immutable` (422), never a silent no-op or a value flip. Don't let the client send `direction` at all here unless it's unchanged.
- **"Delete"** → `DELETE /transactions/{id}` — the action-confirmation shape (§3.2), `transaction.deleted`. The caption under your Delete button ("This removes it from your Base Plan and every plan that inherits it") is accurate for a Base row: deleting it cascades to every overlay any derived plan had on it (`ON DELETE CASCADE`). **Before calling this on a Base row**, consider calling `GET /transactions/{id}/dependents` first (⏳, not yet given its own screen pass) — it returns which plans have an overlay on this transaction, which is what a real confirmation dialog naming affected plans would need; your mockup currently only shows static caption text, not a dynamic per-plan warning.

**Errors on both:** `resource.not_found` (row doesn't exist or belongs to another user — this also covers the case where the id given belongs to an *inherited/overridden* row, since those aren't rows in this table at all; the client must never reach these two routes for anything but an `own`/`added` origin — see §7's origin table).

### 8.3 Editing an inherited/overridden row (screen 5 in your screenshots — the "Modified" badge)

This screen never touches `/transactions/{id}` at all — every action on it goes through the overlay endpoints (§7 already covers where `overlay_id` comes from: the same list response that got the user here).

| Button | Call | Effect |
|---|---|---|
| **Save changes** (row already `overridden`, i.e. has an `overlay_id`) | `PATCH /scenarios/{id}/overlays/{overlay_id}` with the changed `ovr_*` fields (`ovr_amount_minor`, `ovr_name`, `ovr_category_id`, `ovr_recurrence`, `ovr_start_date`, `ovr_end_date`/`unset_end_date`) | Updates just the overridden fields; anything not overridden keeps following Base live |
| **Save changes** (row currently `inherited`, no overlay yet — not shown in your screenshots, but the same screen reached before any field is changed) | `POST /scenarios/{id}/overlays` with `op: "override"`, `base_transaction_id` = the row's own `id`, plus the `ovr_*` fields that differ from Base | Creates the override for the first time |
| **Revert to Base** | `DELETE /scenarios/{id}/overlays/{overlay_id}` | Deletes the overlay entirely — row goes back to plain `inherited`, following Base exactly, live. Same action-confirmation message as everywhere else (`overlay.deleted`, *"Change reverted to Base"*) |
| **Remove from this plan**, row is `inherited` | `POST /scenarios/{id}/overlays` with `op: "exclude"`, `base_transaction_id` = the row's `id` | Row becomes `excluded` (§7) |
| **Remove from this plan**, row is `overridden`/`"Modified"` (as in your screenshot) | **Two calls, not one:** `DELETE /scenarios/{id}/overlays/{overlay_id}` (drops the override) then `POST /scenarios/{id}/overlays` with `op: "exclude"` on the same `base_transaction_id` | An overlay's `op` can never flip from override to exclude in place — a deliberate backend rule (`overlay_service.py`'s own docstring: *"'Remove from this plan' and overriding a value are distinct user actions, not the same overlay reinterpreted"*). **Don't surface the first call's response message to the user** (`"Change reverted to Base"` is a side-effect of the mechanism, not what happened from the user's point of view) — show your own "Removed from this plan" copy only once the second call succeeds. |

Verified live end to end: override Rent's amount, edit the override again, then remove it from the plan via the two-call sequence above — confirmed it disappears from `filter=active` and appears under `filter=removed` with the correct `overlay_id`, and that a plain single-call **Revert to Base** on a still-overridden row restores it to `inherited` correctly (same mechanism already covered in §7's restore test).

**Errors:** same overlay error codes as everywhere else — `overlay.target_not_in_base` (422, wrong `base_transaction_id`), `overlay.already_exists` (409, only relevant if you skip the delete step above and try to create a second overlay on a target that still has one), `overlay.scenario_is_base` (422, these routes reject being called on the Base Plan itself), `resource.not_found` (bad `overlay_id`/`scenario_id`), plus the same `transaction.*` validation codes as create (an override that would make the merged amount ≤ 0, etc.).

### 8.4 Schedule picker

The seven options in your Schedule sheet map exactly to the backend's `recurrence` values — no gaps, nothing to reconcile:

| Sheet label | `recurrence` value |
|---|---|
| One time | `one_time` |
| Weekly | `weekly` |
| Every 2 weeks | `biweekly` |
| Monthly | `monthly` |
| Quarterly | `quarterly` |
| Every 6 months | `semiannual` |
| Yearly | `annual` |

The sheet's caption about a 29th–31st start date "falling on the last day in shorter months" describes the engine's clamp behavior for month-based recurrences — purely informational copy, not something the client computes; the server always returns the already-clamped occurrence dates.

### 8.5 Category picker (as used from this screen)

`GET /categories` returns system categories (`user_id: null`, translated client-side by `key`) plus the caller's own. **The system set was just replaced to match this exact picker** (migration `0015`) — 12 keys: income `salary`, `freelance`, `business`; expense `housing`, `loans`, `bills`, `subscriptions`, `everyday`, `transport`, `fuel`, `health`, `other`. **The picker doesn't filter by the transaction's own direction** — your mockup shows income and expense categories together in one grid for an expense transaction, and that matches the backend exactly: nothing rejects an expense transaction using an income-keyed category or vice versa. Full `GET`/`POST`/`PATCH`/`DELETE /categories` request/response contracts are still ⏳, held for the Categories screen's own turn.

---

## 9. Plans screen — full lifecycle, plus the list's summary data ✅ Verified

**Figma screens:** Plans list, Plan setup sheet (rename / archive / duplicate / delete).

### 9.1 List — `GET /scenarios?include_archived=`

`items`: one `ScenarioOut` per plan — `id`, `name`, `is_base`, `current_balance_override_minor`, `archived_at`, `created_at`, `updated_at`. Default (`include_archived` omitted or `false`) excludes archived plans; `?include_archived=true` includes them too, distinguishable by a non-null `archived_at`.

### 9.2 Rename — `PATCH /scenarios/{id}`

`{"name": "Buy a House v2"}`. Verified: renaming never touches any balance — the sheet's caption ("Renaming does not change any of its numbers") is accurate. **Errors:** `scenario.name_taken` (409), `validation.invalid` (422, blank/whitespace name — same rule as plan creation, §6), `resource.not_found`.

### 9.3 Archive / Unarchive

`POST /scenarios/{id}/archive` sets `archived_at`; `POST /scenarios/{id}/unarchive` clears it back to `null`. Both take no body. Verified round-trip, plus: **Base rejects archiving** with `scenario.base_immutable` (409 — matches the "NEVER DELETABLE" badge, which covers archiving too, not just deleting), and **unarchiving a plan that isn't archived** rejects with `scenario.not_archived` (409). An archived plan is excluded from the default list, the compare picker, and duplicate-source eligibility (`scenario.archived`, 409, if attempted anyway).

### 9.4 Duplicate — `POST /scenarios/{id}/duplicate`

`{"name": "optional — omit for '<source name> (copy)'"}`. **Verified the sheet's caption word for word** ("The copy keeps live Base inheritance, plus all overrides, removals and plan-only items."): duplicated a plan with one override, one exclude ("removal"), and one added transaction — the copy reproduced all three exactly, while everything untouched kept following Base live (the normal inheritance behavior, unaffected by the copy). **Errors:** `scenario.archived` (409, can't duplicate an archived source — restore it first), `scenario.name_taken`/`validation.invalid` (same name rules as create), `resource.not_found`.

### 9.5 Delete — `DELETE /scenarios/{id}`

Action-confirmation shape (§3.2), `scenario.deleted`. **Base rejects with `scenario.base_immutable`** (409) — confirms the "NEVER DELETABLE" badge.

### 9.6 Deriving the list card's numbers (Balance at 10Y, vs Base, "X modified · Y removed · Z added") — no new endpoint, combine two existing calls

`horizon=120` is exactly **10 years** (the backend's `max_horizon_months` is 120) — that's the number to request for "Balance at 10Y" everywhere on this screen.

- **Base's own card:** `GET /scenarios/{base_id}/forecast?horizon=120` → `totals.closing_balance_minor` is "Balance at 10Y". No delta, no modified/removed/added line — nothing to compare Base against.
- **Every other plan's card**, two calls:
  1. `GET /forecast/compare?a={base_id}&b={plan_id}&horizon=120` → `b.totals.closing_balance_minor` is that plan's "Balance at 10Y"; `deltas[-1].closing_balance_delta_minor` is "vs Base" (negative → red, positive → green, matching your mockup).
  2. `GET /scenarios/{plan_id}/transactions?filter=all` → count `items` by `origin`: `overridden` → **modified**, `excluded` → **removed**, `added` → **added** (ignore `inherited`/`own`).
- **Why two calls, not one:** `compare`'s own `drivers` list (tagged `added`/`removed`/`modified`) looks like a shortcut for the same three counts, but it's the wrong source — a driver only appears there when the change actually moves the total. **Verified live:** overriding a transaction's *name only* (same amount) produced **zero drivers** in `compare`, while `transactions?filter=all` correctly still showed it as `origin: "overridden"`. Since that same row shows a `Modified` badge everywhere else in the app (§7), the two counts must agree — use `filter=all`'s origin counts for this line, not `compare`'s drivers.
- This means rendering the full Plans list costs **1 call for Base's card, plus 2 calls per other plan.** There's deliberately no dedicated list-summary/aggregation endpoint — matches the architecture's standing "no dashboard, no charts endpoint" rule (every number on every screen comes from the forecast/compare/transactions payloads that already exist for other reasons). Worth revisiting only if a user's plan count grows large enough that this becomes a lot of requests to render one screen — there's no cap on plan count at all (see `backend-plan/12-open-questions-and-future-hardening.md`).

Note: this section only verifies the specific fields above for this exact purpose — the full forecast/compare contract (month rows, full driver detail, for actual chart/dashboard screens) is still ⏳, held for the Forecast and Compare screens' own turns.

### 9.7 Error code summary for this screen

| `code` | HTTP | When |
|---|---|---|
| `scenario.name_taken` | 409 | Create/rename/duplicate name collides with an existing plan (including Base's own name, and archived plans) |
| `scenario.base_immutable` | 409 | Attempt to archive or delete the Base Plan |
| `scenario.archived` | 409 | Attempt to duplicate an archived plan, or use one as a compare operand |
| `scenario.not_archived` | 409 | Attempt to unarchive a plan that isn't archived |
| `validation.invalid` | 422 | Blank/whitespace name |
| `resource.not_found` | 404 | Plan doesn't exist or belongs to another user |

---

## 10. Compare plans ✅ Verified

**Figma screens:** Compare plans (picker), Compare results.

### 10.1 The picker's per-plan "+SAR X/mo" preview

Shown next to each non-Base plan before you've even picked which two to compare (Base's row shows "Your real numbers" instead — nothing to compute there). **This is not a comparison at all** — it's that plan's own standalone average monthly cash flow, independent of Base: call `GET /scenarios/{id}/forecast?horizon=` (whatever the currently-selected horizon pill is) for each plan shown, and divide `totals.net_minor / horizon_months`. Verified live: sign and magnitude behave exactly as expected for a plan whose own income comfortably exceeds its own expenses.

### 10.2 Running the comparison — `GET /forecast/compare?a=&b=&horizon=&anchor=`

- `a`, `b` — the two plan ids ("Pick exactly two plans"). Order doesn't matter for validation, but the response's `a`/`b` keys mirror whichever you passed — keep Plan A/Plan B on the client side consistent with which id went where.
- `horizon` — the four pills map directly: 1Y→`12`, 3Y→`36`, 5Y→`60`, 10Y→`120`.
- `anchor` — omit it; defaults to the user's `balance_as_of` month, identically for both sides (already covered by D-14 — there's no reason for this screen to ever pass one explicitly).

**Errors:** `compare.same_scenario` (422, A and B are the same plan — enforce "pick two *different* plans" client-side too, for instant feedback), `scenario.archived` (409, either operand is archived — archived plans should already be excluded from this picker's list, e.g. by calling `GET /scenarios` without `include_archived`), `forecast.invalid_horizon` (422), `resource.not_found`.

### 10.3 "Compare results" — mapping the response to the screen

| Screen element | Field |
|---|---|
| Plan A name/balance (solid line legend) | `a.scenario_id` (look up the name client-side) / `a.totals.closing_balance_minor` |
| Plan B name/balance (dashed line legend) | `b.scenario_id` / `b.totals.closing_balance_minor` |
| "Difference at 10 years" amount | `deltas[-1].closing_balance_delta_minor` |
| "Difference at 10 years" percentage | `deltas[-1].closing_balance_delta_pct` — **can be `null`** ("baseline is 0" case); render "—", never `0%` or an error |
| Chart, solid line | `a.months[].closing_balance_minor`, in order |
| Chart, dashed line | `b.months[].closing_balance_minor`, in order |
| "Month by month" table | `a.months[]`/`b.months[]` (or `deltas[]` for the DIFF column) — pick whichever rows you want to show (e.g. every 12th for a yearly table); the full monthly array is always there, this screen just doesn't render every row |

### 10.4 "What's driving this" — the `drivers` list

Already ranked by impact server-side (largest absolute contribution first) — render in the order given, no client-side sorting needed.

| Screen element | Field |
|---|---|
| Row order | Already sorted by `abs(total_contribution_minor)` descending |
| Item name | `name` |
| Badge | `change` — `"modified"` → **Modified**, `"added"` → **Only in this plan**, `"removed"` → **Removed** |
| "$X/mo" figure, color | `total_contribution_minor / active_months` — **not** `/ horizon_months`. Negative → red (this plan is worse off because of this item), positive → green. |

**Why `active_months`, not `horizon_months`:** a driver's `total_contribution_minor` is summed over however many months it actually occurred in — for a mortgage added 2 months into a 120-month comparison, that's 118 months, not 120. Dividing by the full horizon dilutes the figure (this exact case showed SAR 8,850/mo instead of its real SAR 9,000/mo before this was fixed). `active_months` is the divisor that gives the item's true, steady per-occurrence rate. Verified live with exactly this scenario.

**Errors on this response:** same as §10.2 (this is one call, not two — `drivers` and `deltas` both come back together with `a`/`b`).

---

## 11. Profile — name & photo ✅ Verified

**Figma screen:** Profile (avatar, "Change photo", Full Name, Email, Save changes).

**Everything on this screen — name and photo together — goes through the same call already covered in §9.6's brief mention: `PATCH /me/settings`.** There is deliberately no separate upload endpoint for the photo; it's one more optional field on the same request that already handles `display_name`/`currency_code`/`locale`.

### 11.1 Request

```json
{
  "display_name": "Muhammad",
  "avatar_base64": "iVBORw0KGgoAAAANSUhEUgAA..."
}
```

- **`avatar_base64`** — the raw base64-encoded image bytes. A `data:image/png;base64,...` prefix is also accepted and stripped automatically — send whichever your image picker hands you, no need to strip it client-side.
- **`remove_avatar: true`** — clears the photo back to none (deletes the stored file). Don't send this alongside `avatar_base64` in the same request; `remove_avatar` wins if both are present.
- Every field is optional/patch-style, same as every other call to this endpoint — send only what changed. "Save changes" on this screen in practice only ever sends `display_name` and, if the user tapped "Change photo," `avatar_base64`.
- **Email is not sent here at all — it's read-only.** There is no way to change an account's email in Phase 1 (decided explicitly: no verification flow exists without an email provider, and re-locking it down after account creation was simpler than building a real change-email flow around that gap). Render the Email field as **display-only**, never submit it.

### 11.2 Response

Same `MeOut`/`SettingsOut` shape as everywhere else this endpoint appears. The new field:

```json
{
  "settings": {
    "display_name": "Muhammad",
    "avatar_url": "/static/avatars/e39c420b-448e-4f3c-bc67-3acf32e44cae.png",
    "currency_code": "SAR",
    "locale": "en",
    "current_balance_minor": 0,
    "balance_as_of": "2026-09-16"
  }
}
```

**`avatar_url` is `null` until a photo is ever uploaded, then a relative path** — not a full URL. Prepend your app's own configured base host (the same one from §1, **without** the `/v1` suffix — this route isn't versioned, it's a static file mount, not part of the JSON API). E.g. base `http://10.0.2.2:8000` + `avatar_url` → `http://10.0.2.2:8000/static/avatars/e39c420b-....png`. The route is unauthenticated (no `Authorization` header needed to load the image itself) — anyone with the exact URL can view it, but filenames are random UUIDs, never sequential or derived from the user id, so there's nothing to enumerate.

### 11.3 Errors

| `code` | HTTP | When |
|---|---|---|
| `avatar.invalid_image` | 422 | The bytes don't start with a recognized image signature (JPEG/PNG/WEBP) — this includes a corrupt/truncated upload or base64 that fails to decode at all |
| `avatar.too_large` | 422 | Decoded image exceeds **5MB** |
| `validation.invalid` | 422 | Other field-level issues |
| `resource.not_found` | 404 | Shouldn't happen for the caller's own profile — same generic guard as everywhere else |

**Re-uploading replaces the old photo — the old file is deleted from disk once the new one is written successfully.** A rejected upload (wrong format, too large) never touches the existing photo; validation happens before anything is written or deleted.

**Storage note, worth knowing even though it doesn't change the contract:** this is local-disk storage on whichever machine runs the backend, explicitly acknowledged as a Phase 1-only choice — it will need to move to real object storage the moment this runs somewhere with an ephemeral or non-shared filesystem (most real hosting). Nothing about the request/response shape above should change when that happens; only what `avatar_url` resolves to.

---

## 12. Settings screen ✅ Verified

**Figma screen:** Settings (Profile card, Currency, Language, Opening balance, Change password, Export data, Reset data, Delete account, About, Log out).

Every row on this screen maps to something already covered elsewhere in this document — this section is the map, not new contract detail.

| Row | Backend | Notes |
|---|---|---|
| Profile card / **Profile** | §11 | Name + photo. Tapping through opens the Profile screen already covered there. |
| **Currency** | — | **Frontend-only.** The currency list is a static client-side picker (§10.1 already covers `currency_code` itself — free-form, no server-side whitelist, by earlier explicit decision). Selecting one calls `PATCH /me/settings` with `currency_code` — no new contract. |
| **Language** | — | **Frontend-only** in the same sense — which languages are offered is a client concern. Selecting one calls `PATCH /me/settings` with `locale` (`"en"`/`"ar"`) — already built, no new contract. This is also what the server uses to pick `message_en` vs. `message_ar` in every response (§3.1). |
| **Opening balance** | §5 (`PUT /me/balance`) | Re-verified live for this screen: same endpoint as the initial onboarding entry, works identically from Settings. **Naming note, not a backend issue:** the mockup labels this "Opening balance," but the screen-flow spec's own signed rule (§10, "the one naming rule in the product with a signed rule behind it") is that this figure is always called **"Current Cash Balance"** in user-facing copy, specifically *not* "opening balance" — worth a look before this ships, though nothing here blocks backend work either way; the field is `current_balance_minor` regardless of what label the screen puts next to it. |
| **Change password** | §15's `auth.current_password_incorrect`/`auth.weak_password` (endpoint: `PATCH /me/password`, built in the password-reset-removal work) | Re-verified live: succeeds with the right current password, old sessions revoked. |
| **Export data** | ⏳ (built, not yet given this screen's own detailed pass) | `GET /me/export?format=csv\|json` — re-verified live, both formats return correctly (`csv` → `application/zip`, `json` → `application/json`). Matches "available in two formats" exactly. |
| **Reset data** | ⏳ (built, not yet given this screen's own detailed pass) | `DELETE /me/data` — re-verified live against this screen's exact description ("resets the account, deleting all plans and transactions and data, just keeping account info"): after reset, only the Base Plan remains (empty), every derived plan is gone, user-created categories are gone, balance resets to 0/today — but email, display name, avatar, currency, and locale are all untouched. |
| **Delete account** | `backend-plan/12-open-questions-and-future-hardening.md` §9 item 9 (soft delete) | `DELETE /me` — re-verified live as a **soft delete**: looks and behaves like a hard delete to the app (can't log in, every token dead immediately, same email works again on a fresh signup right away), while the row and its data physically survive on the server for a Phase 2 purge job that doesn't exist yet. Nothing for the client to do differently than it would for an actual hard delete — same call, same response, same follow-up behavior (log out / return to Sign Up). |
| **About Horizon**, **Log out** | — | No backend involvement — About is static app info; Log out is `POST /auth/logout` (§4). |

---

## 13. Home screen ✅ Verified

**Figma screen:** Home (plan switcher, greeting, Current cash balance, period selector + chart, Net cash flow / Projected balance / Outlook, Add transaction, Recent transactions).

Every number on this screen comes from calls already covered elsewhere in this document. This section maps the screen to those calls and covers the one genuinely new piece: the "This Month" tab's weekly chart.

### 13.1 What maps to what

| Screen element | Source |
|---|---|
| Plan switcher, greeting (name + photo), gear → Settings | `GET /scenarios` (§9.1), `GET /me` (§11) |
| **Current cash balance** SAR 72,400 | `current_balance_minor` (§5/§11) |
| **"Base Plan +SAR 9,043/mo"**, **"Net cash flow +SAR 9,043 this month"** | The **current month's** `net_minor` — `GET /scenarios/{id}/forecast`, find the row in `months[]` whose `month` equals `current_month` (both already in the payload, §9.6). Same figure both places on this screen — not a horizon-wide average. |
| **"Projected balance SAR 81,443"** | The current month's `closing_balance_minor` from that same row. (Sanity check: `72,400 + 9,043 = 81,443` exactly — confirmed live.) |
| **Outlook: Improving** | Purely client-side (M1 §11 decision, `12-open-questions-and-future-hardening.md` §8 item 4) — computed from `months[]`, no backend involvement, rule intentionally left open until this screen is actually built. |
| Add / Forecast / Plans / Plan setup buttons | Navigation only |
| **Recent transactions + "See all"** | `GET /scenarios/{id}/transactions` (§7) — this screen just renders the first few rows of the same list the Transactions screen shows in full |
| **3 Months / 6 Months / 12 Months tabs** | One point per month, straight from `months[]` — no new data needed, same payload as "This Month" just read differently |

### 13.2 "This Month"'s weekly chart — new: `?include_occurrences=true`

The curved W1–W4 line needs day-dated detail a monthly total can't give you (income landing on the 1st vs. a car loan on the 5th moves the curve differently week to week). `GET /scenarios/{id}/forecast` gained an opt-in query param for exactly this:

```
GET /scenarios/{id}/forecast?horizon=1&anchor=2026-09&include_occurrences=true
```

**Default is `false` — every existing caller of this endpoint (the Plans list summary §9.6, the Compare screen §10) is completely unaffected and never pays for this data.** `GET /forecast/compare` has no equivalent param at all; its `a`/`b` always omit `occurrences` (`null`), since that screen's chart is monthly-level.

**Response** — `occurrences` is `null` unless requested, otherwise a flat list, unsorted (bucket/sort client-side):

```json
{
  "months": [{"month": "2026-09", "income_minor": 2050000, "expense_minor": 630000, "net_minor": 1420000, "closing_balance_minor": 8660000}],
  "occurrences": [
    {"source_id": "cb90692d-...", "name": "Rent", "direction": "expense", "amount_minor": 450000, "on": "2026-09-01"},
    {"source_id": "db29f831-...", "name": "Salary", "direction": "income", "amount_minor": 1800000, "on": "2026-09-01"},
    {"source_id": "25951e26-...", "name": "Car loan", "direction": "expense", "amount_minor": 180000, "on": "2026-09-05"},
    {"source_id": "4feb4ed8-...", "name": "Freelance work", "direction": "income", "amount_minor": 250000, "on": "2026-09-20"}
  ]
}
```

**Building the weekly curve is entirely client-side work:** bucket `occurrences` into whatever 7-day (or calendar-week) windows you choose — the server deliberately doesn't define "a week within a month" (months don't divide evenly into weeks, and no locked doc specifies a rule), so there's nothing to disagree with. Starting balance for the curve is the **previous** month's `closing_balance_minor` (or `current_balance_minor` if this is the very first month in the ledger); each week's point is that running total plus the signed sum of every occurrence up to that week's end.

**For horizons larger than one month** (if you ever want week-level detail across more than the current month), request occurrences the same way — just know the list grows with the horizon, so keep `include_occurrences=true` for small, targeted requests (like this screen's `horizon=1`), not for a 10-year pull.

---

## 14. Full endpoint index (status of every endpoint that exists)

Detailed contracts for these land above (or in their own section) once their Figma screen is walked through. Method/path/purpose here is accurate and already fully built+tested server-side — see `backend-plan/08-api-endpoints-plan.md` for the internal version of this same table if you need something ahead of its screen's turn.

| Area | Endpoint | Status |
|---|---|---|
| Auth | `POST /auth/register` | ✅ §4 |
| Auth | `POST /auth/login` | ✅ §4 |
| Auth | `POST /auth/refresh` | ✅ §4 |
| Auth | `POST /auth/logout` | ✅ §4 |
| Me / Settings | `GET /me` | ✅ §5 |
| Me / Settings | `PATCH /me/settings` | ✅ §11 |
| Me / Settings | `PUT /me/balance` | ✅ §5 |
| Me / Settings | `PATCH /me/password` | ⏳ |
| Me / Settings | `DELETE /me` | ✅ §12 |
| Categories | `GET /categories` | ⏳ |
| Categories | `POST /categories` | ⏳ |
| Categories | `PATCH /categories/{id}` | ⏳ |
| Categories | `DELETE /categories/{id}` | ⏳ |
| Plans | `GET /scenarios?include_archived=` | ✅ §9 |
| Plans | `POST /scenarios` | ✅ §6 |
| Plans | `GET /scenarios/{id}` | ⏳ |
| Plans | `PATCH /scenarios/{id}` | ✅ §9 |
| Plans | `DELETE /scenarios/{id}` | ✅ §9 |
| Plans | `POST /scenarios/{id}/duplicate` | ✅ §9 |
| Plans | `POST /scenarios/{id}/archive` | ✅ §9 |
| Plans | `POST /scenarios/{id}/unarchive` | ✅ §9 |
| Transactions | `GET /scenarios/{id}/transactions?filter=` | ✅ §7 |
| Transactions | `POST /scenarios/{id}/transactions` | ✅ §8 |
| Transactions | `PATCH /transactions/{id}` | ✅ §8 |
| Transactions | `DELETE /transactions/{id}` | ✅ §8 |
| Transactions | `GET /transactions/{id}/dependents` | ⏳ |
| Overlays | `POST /scenarios/{id}/overlays` | ✅ §8 |
| Overlays | `PATCH /scenarios/{id}/overlays/{ovid}` | ✅ §8 |
| Overlays | `DELETE /scenarios/{id}/overlays/{ovid}` | ✅ §8 |
| Forecast & Compare | `GET /scenarios/{id}/forecast?horizon=&anchor=&include_occurrences=` | ✅ §13 |
| Forecast & Compare | `GET /forecast/compare?a=&b=&horizon=&anchor=` | ✅ §10 |
| Account data | `DELETE /me/data` | ✅ §12 |
| Account data | `GET /me/export?format=` | ✅ §12 |

---

## 15. Error code reference (all codes, every endpoint)

Every code below always comes with a `message_en`/`message_ar` pair (§3.1) — this table exists for the `code` values themselves, to branch client logic on.

| Code | HTTP | Meaning |
|---|---|---|
| `auth.invalid_credentials` | 401 | Email or password is wrong |
| `auth.email_taken` | 409 | Registration attempted with an email already in use |
| `auth.token_expired` | 401 | Access token expired — refresh and retry |
| `auth.token_invalid` | 401 | Malformed, unknown, or revoked token |
| `auth.weak_password` | 422 | Password below policy |
| `auth.current_password_incorrect` | 422 | `PATCH /me/password`'s current-password check failed |
| `balance.as_of_in_future` | 422 | `PUT /me/balance`'s as-of date is later than today |
| `balance.as_of_too_old` | 422 | `PUT /me/balance`'s as-of date is more than 5 years ago |
| `balance.negative_not_allowed` | 422 | `PUT /me/balance`'s amount is negative |
| `avatar.invalid_image` | 422 | `PATCH /me/settings`'s `avatar_base64` isn't a recognized image format (or fails to decode at all) |
| `avatar.too_large` | 422 | `PATCH /me/settings`'s decoded `avatar_base64` exceeds the size limit (5MB) |
| `validation.required` | 422 | A required field is missing (`params.field` names it) |
| `validation.invalid` | 422 | Generic field validation failure |
| `transaction.amount_not_positive` | 422 | Amount is zero or negative |
| `transaction.end_before_start` | 422 | End date precedes start date |
| `transaction.one_time_has_end_date` | 422 | A one-time transaction was given an end date |
| `transaction.direction_immutable` | 422 | Attempt to flip income ↔ expense on an existing transaction |
| `scenario.base_immutable` | 409 | Attempt to delete or archive the Base plan |
| `scenario.name_taken` | 409 | Duplicate plan name for this user |
| `scenario.archived` | 409 | An archived plan used as a comparison operand or duplicate source |
| `scenario.not_archived` | 409 | Unarchive attempted on a plan that isn't archived |
| `overlay.target_not_in_base` | 422 | An overlay was pointed at a transaction that isn't in Base |
| `overlay.already_exists` | 409 | A second overlay was attempted against the same target |
| `overlay.scenario_is_base` | 422 | An overlay was attempted on the Base plan itself |
| `category.in_use` | 409 | Deleting a category still referenced by a transaction or override |
| `compare.same_scenario` | 422 | Plan A and Plan B are the same plan |
| `forecast.invalid_horizon` | 422 | Horizon is outside the allowed range |
| `resource.not_found` | 404 | Also returned for another user's resource — never distinguishable from "doesn't exist" |
| `rate_limited` | 429 | Too many attempts on a rate-limited route (login/register: 5/min per IP) |
| `internal` | 500 | Unhandled server error — report the `request_id` |

**`resource.not_found` for someone else's data is deliberate, not a bug** — a 403 would confirm the resource exists at all, which is itself a leak in a financial product. Treat it as "this id doesn't exist" in the UI either way.

---

## 16. Open items that affect integration

- **Arabic text is unreviewed** (§3.1) — display it, but expect it to be replaced with native-speaker-reviewed copy later without any contract change.
- **No forgot/reset-password-via-email in this phase** — a user who forgets their password has no self-service recovery until Phase 2; the only password change path is `PATCH /me/password` while logged in (requires the current password). Design the Login screen's "forgot password?" affordance accordingly — either omit it for now or show it as "coming soon."
- **No production/staging base URL yet** — deployment is deliberately held; §1's local URLs are all that exist right now.
