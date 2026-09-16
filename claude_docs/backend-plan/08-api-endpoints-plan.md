# API Endpoints Plan

This is the API-wise plan: every endpoint the backend exposes in Phase 1, grouped by resource, with what each one does, what it needs, and which error codes it can produce. Reference `07-api-layer-and-error-handling.md` for the shared conventions (error envelope, `_minor` suffixes, `items` wrapping) — they aren't repeated per endpoint below.

All routes below sit under `/v1` and (except the ones marked public) require a valid access token, with every underlying query scoped to the caller's `user_id`.

## 1. Auth (public)

| Endpoint | Purpose | Key error codes |
|---|---|---|
| `POST /auth/register` | Create a user (email, password, name) + their Base scenario + default settings in one step. `name` is required and stored as `user_settings.display_name` at creation time — never null for a new user. | `auth.email_taken`, `auth.weak_password`, `validation.*` |
| `POST /auth/login` | Exchange credentials for an access + refresh token pair | `auth.invalid_credentials`, `rate_limited` |
| `POST /auth/refresh` | Exchange a refresh token for a new access/refresh pair; rotates the refresh token; reuse of an already-consumed token revokes the whole family | `auth.token_invalid`, `auth.token_expired` |
| `POST /auth/logout` | Revoke the current refresh token family | `auth.token_invalid` |

## 2. Me / Settings

| Endpoint | Purpose | Key error codes |
|---|---|---|
| `GET /me` | Current user's identity/profile basics | — |
| `PATCH /me/settings` | Update currency, locale, display name — **not** the Current Cash Balance (see below) | `validation.*` |
| `PUT /me/balance` | The *only* write path for the Current Cash Balance + its as-of date (D-04, architecture §9.1). Same endpoint for both the initial onboarding entry and any later edit (Settings → F5/B3) — there's no separate "set once" call. | `balance.as_of_in_future`, `balance.as_of_too_old`, `balance.negative_not_allowed` |
| `PATCH /me/password` | The *only* way to change a password in Phase 1 — no forgot/reset-password-via-email flow (see `09-auth-and-security.md` §5). Requires the current password re-entered plus the new one; revokes every other session | `auth.current_password_incorrect`, `auth.weak_password` |
| `DELETE /me` | Permanent account deletion (screen-flow F9), distinct from `/me/data` reset below. Not in the architecture doc's locked §9 list — built as a small addition, see `12-open-questions-and-future-hardening.md` §3 | — |

Note: **Current Cash Balance changes are consequential** — every scenario's forecast shifts. Deliberately split into its own endpoint rather than folded into settings, so that consequence stays visible in the API, the logs and the client code (architecture §9.1). The API accepts a well-formed change unconditionally beyond the two date guards above; the screen-flow spec's requirement for a "preview the effect before confirming" experience is a client-side concern (the client can call the forecast endpoint with a hypothetical value before committing, if that pattern is chosen — no special backend support is needed for it).

## 3. Categories

| Endpoint | Purpose | Key error codes |
|---|---|---|
| `GET /categories` | List system categories (translated client-side by `key`) plus the caller's own user-defined ones | — |
| `POST /categories` | Create a user category (name + direction only, no `key`) | `validation.*` |
| `PATCH /categories/{id}` | Rename and/or change direction of a user-owned category | — |
| `DELETE /categories/{id}` | Delete a user-owned category | `category.in_use` |

Built as a small addition beyond the architecture doc's locked §9 surface (see `12-open-questions-and-future-hardening.md` §3). All four CRUD operations on a user category are now built. Ownership enforcement follows the same convention as everywhere else (09 §3): a system category or another user's category is 404-equivalent to PATCH/DELETE, never a distinguishable "forbidden." Deleting a category still referenced by a transaction or an overlay's override is rejected with `category.in_use` (409) rather than surfacing the underlying FK error.

## 4. Scenarios (Plans)

| Endpoint | Purpose | Key error codes |
|---|---|---|
| `GET /scenarios?include_archived=` | List the caller's plans | — |
| `POST /scenarios` | Create a plan (optionally with a starting-balance override) | `scenario.name_taken`, `validation.*` |
| `GET /scenarios/{id}` | Plan detail | `resource.not_found` |
| `PATCH /scenarios/{id}` | Rename, change the Current Cash Balance override (amount only — D-14) | `scenario.base_immutable` (if attempted on Base for a field that shouldn't move), `resource.not_found` |
| `DELETE /scenarios/{id}` | Delete a plan | `scenario.base_immutable`, `resource.not_found` |
| `POST /scenarios/{id}/duplicate` | Copy a plan's own transactions and overlays (no parent link created) | `scenario.archived` (archived scenarios can't be a duplicate source — architecture §6.2), `resource.not_found` |
| `POST /scenarios/{id}/archive` | Archive | `scenario.base_immutable`, `resource.not_found` |
| `POST /scenarios/{id}/unarchive` | Restore from archive | `scenario.not_archived`, `resource.not_found` |

## 5. Transactions

| Endpoint | Purpose | Key error codes |
|---|---|---|
| `GET /scenarios/{id}/transactions?filter=` | The **resolved** view of a scenario — every row carries `origin` (own/inherited/overridden/added/**excluded**), which is exactly what the UI's badge system renders from. `filter` is `active` (default, unchanged original behavior), `removed` (only excluded rows — always empty on Base), or `all` (both). Every overridden/excluded row carries `overlay_id`, so the client can call the overlay endpoints on a row it's looking at without a separate lookup. | `resource.not_found`, `validation.invalid` (bad `filter`) |
| `POST /scenarios/{id}/transactions` | Create a transaction local to this scenario (`origin = added`) | `transaction.*`, `validation.*` |
| `PATCH /transactions/{id}` | Edit a transaction the caller owns directly (i.e. `origin = own` in Base, or `origin = added` in a derived scenario) | `transaction.direction_immutable`, `transaction.end_before_start`, `transaction.one_time_has_end_date`, `resource.not_found` |
| `DELETE /transactions/{id}` | Delete a transaction the caller owns directly | `resource.not_found` |
| `GET /transactions/{id}/dependents` | Scenarios holding an overlay on this transaction (architecture §6.3) — lets the client warn before deleting a Base row that other plans have overridden or excluded | `resource.not_found` |

**Critical routing rule, restated because it's the single riskiest interaction in the product:** editing or removing a row whose `origin` is `inherited` or `overridden` does **not** hit these two PATCH/DELETE routes at all — it goes through the overlay endpoints below instead. The client is responsible for choosing the right call based on the `origin` it was shown (architecture §9.2, screen-flow §4.4); this backend enforces the *result* of that rule (overlays can only target Base transactions, Base transactions are never mutated from a scenario context) but cannot stop a client from calling the wrong endpoint — which is exactly why this gets its own emphasis in the mobile handoff.

## 6. Overlays

| Endpoint | Purpose | Key error codes |
|---|---|---|
| `POST /scenarios/{id}/overlays` | Create an `exclude` or `override` overlay against a Base transaction | `overlay.target_not_in_base`, `overlay.already_exists`, `validation.*` |
| `PATCH /scenarios/{id}/overlays/{ovid}` | Edit an existing overlay (e.g. change the override's amount) | `resource.not_found` |
| `DELETE /scenarios/{id}/overlays/{ovid}` | Remove an overlay — the transaction reverts to plain inheritance from Base | `resource.not_found` |

## 7. Forecast & Compare

| Endpoint | Purpose | Key error codes |
|---|---|---|
| `GET /scenarios/{id}/forecast?horizon=&anchor=` | The one payload that feeds the dashboard, all three forecast chart views, the monthly table, and month breakdown | `forecast.invalid_horizon`, `resource.not_found` |
| `GET /forecast/compare?a=&b=&horizon=&anchor=` | Two ledgers aligned by month, plus deltas and the drivers list | `compare.same_scenario`, `scenario.archived` (either operand — architecture §6.2), `forecast.invalid_horizon`, `resource.not_found` |

`anchor` is optional on both and, if omitted, defaults to the month of `user_settings.balance_as_of` — never today's clock — resolved in `ForecastService`, never inside the engine (see `06-services-module.md`). `balance_as_of` is user-level (D-14), so an omitted anchor on `/forecast/compare` defaults identically for both operands. Accepting an explicit anchor is what lets a fixed test case or a client bug report be reproduced exactly, at zero extra cost. `horizon` accepts any value in `[1, max_horizon_months]`, not just the four client-facing presets (12/36/60/120) — the dashboard requests `months_elapsed + 12`, which usually isn't one of them.

There is deliberately no `/dashboard` and no `/charts` endpoint anywhere in this plan — every screen that shows a number renders it from one of the two payloads above.

## 8. Account data

| Endpoint | Purpose | Key error codes |
|---|---|---|
| `DELETE /me/data` | Full reset (RFP §4.8) | — |
| `GET /me/export?format=` | Full raw backup of the user's data (RFP §4.8), as `json` (default) or `csv` — CSV bundles five files, one per table, as a ZIP, since a single flat CSV can't hold five differently-shaped tables | `validation.invalid` (bad `format` value) |

`DELETE /me` (full account deletion, distinct from a data reset) is listed under §2 above, not here — it lives on the account resource itself, not "data."
