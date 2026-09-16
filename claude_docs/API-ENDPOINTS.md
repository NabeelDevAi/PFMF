# Horizon — API Reference (Flutter Integration)

This is the handoff document for Flutter development. It is a **living document**: as each Figma screen is verified against the backend (screen-by-screen, feature by feature), the endpoint(s) it depends on get their full contract written up here — exact request/response shapes, real examples, every error the client needs to handle. Nothing goes in here as a guess; every entry below was hit with a real HTTP request against the running backend before being written down.

For the full endpoint index (every endpoint that exists, whether or not it's been screen-verified yet), see `backend-plan/08-api-endpoints-plan.md` — that's the internal planning doc. This file is the subset of it that's actually been walked through screen-by-screen, in the detail a client needs to integrate against it.

**Status legend:**
- ✅ **Verified** — walked through against a specific Figma screen, contract below is exact and tested.
- ⏳ **Not yet verified** — endpoint exists and is fully tested server-side, but hasn't been matched against its Figma screen yet. Listed in the index (§10) so nothing is forgotten; full contract lands here once its turn comes.

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

Full error code reference: §11 below.

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

## 10. Full endpoint index (status of every endpoint that exists)

Detailed contracts for these land above (or in their own section) once their Figma screen is walked through. Method/path/purpose here is accurate and already fully built+tested server-side — see `backend-plan/08-api-endpoints-plan.md` for the internal version of this same table if you need something ahead of its screen's turn.

| Area | Endpoint | Status |
|---|---|---|
| Auth | `POST /auth/register` | ✅ §4 |
| Auth | `POST /auth/login` | ✅ §4 |
| Auth | `POST /auth/refresh` | ✅ §4 |
| Auth | `POST /auth/logout` | ✅ §4 |
| Me / Settings | `GET /me` | ✅ §5 |
| Me / Settings | `PATCH /me/settings` | ⏳ |
| Me / Settings | `PUT /me/balance` | ✅ §5 |
| Me / Settings | `PATCH /me/password` | ⏳ |
| Me / Settings | `DELETE /me` | ⏳ |
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
| Forecast & Compare | `GET /scenarios/{id}/forecast?horizon=&anchor=` | ⏳ |
| Forecast & Compare | `GET /forecast/compare?a=&b=&horizon=&anchor=` | ⏳ |
| Account data | `DELETE /me/data` | ⏳ |
| Account data | `GET /me/export?format=` | ⏳ |

---

## 11. Error code reference (all codes, every endpoint)

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

## 12. Open items that affect integration

- **Arabic text is unreviewed** (§3.1) — display it, but expect it to be replaced with native-speaker-reviewed copy later without any contract change.
- **No forgot/reset-password-via-email in this phase** — a user who forgets their password has no self-service recovery until Phase 2; the only password change path is `PATCH /me/password` while logged in (requires the current password). Design the Login screen's "forgot password?" affordance accordingly — either omit it for now or show it as "coming soon."
- **No production/staging base URL yet** — deployment is deliberately held; §1's local URLs are all that exist right now.
