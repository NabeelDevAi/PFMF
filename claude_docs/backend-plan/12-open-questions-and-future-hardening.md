# Open Questions & Future Hardening

Everything here is either deliberately deferred (a scope decision made in this planning pass) or genuinely unresolved (waiting on a client/discovery answer). None of it blocks starting M0/M1.

## 1. Deliberately deferred in this build (see `11-build-order-and-milestones.md`, M6)

- ~~`mypy --strict` on the engine module.~~ **Done** (Tier 2 #4): `[tool.mypy]` in `pyproject.toml`, scoped to `files = ["app/engine"]` only -- deliberately not expanded to the rest of the app. Clean on the first run, no fixes needed, since the engine already had full type hints throughout.
- ~~`import-linter`~~ **Done** (Tier 2 #5): both contracts from the original spec (`engine-is-pure`, `layers`) in `[tool.importlinter]`. Its first run caught a real, pre-existing layering violation -- every service imported `APIError` from `app.api.errors`, backwards through the `api -> services -> repositories -> db` direction. Fixed by moving the error registry and `APIError` itself to `app.core.errors` (core sits below both api and services); `app.api.errors` now holds only the FastAPI-specific envelope/exception-handler code. Both contracts pass clean after the fix.
- ~~Hypothesis property-based fuzzing~~ **Done** (Tier 2 #6): all four invariants from architecture §12.3 now run as genuine generated fuzzing, not just the hand-picked cases (which stay, as permanent pinned regression tests -- both layers are additive, not a replacement). Reconciliation/determinism/driver-completeness live in `tests/engine/test_properties.py` (200 examples each, pure engine, `tests/engine/strategies.py` generates realistic transaction sets). Isolation lives in `tests/services/test_scenario_resolver.py` against the real database, using Hypothesis's `st.data()` interleaved-draw pattern so each of 25 examples can create its own fresh user/scenario/overlay state inside one shared `db_session` fixture.
- GitHub Actions CI and coverage gates — considered (Tier 2 #7/#8) and explicitly **skipped by user decision**, not just left deferred: no CI pipeline exists to enforce either, and there's no remote-push cadence yet to make one worth maintaining. Revisit whenever that changes.
- OpenAPI export/regression check — considered (Tier 2 #9) and **skipped**: no mobile consumer yet to protect, and without CI nothing would keep a committed snapshot honest anyway.
- Automated Alembic drift check — considered (Tier 2 #10) and **skipped**, same reasoning: meaningless without the CI pipeline that would enforce it.
- Docker packaging and any deployment story — considered (Tier 3) and **skipped by explicit user decision**: this build stays no-Docker (the original decision at session start), and there's no deployment target yet to design toward. Revisit only once there's an actual decision to deploy somewhere.
- The in-memory rate limiter — fine for one local process, not fine the moment there's more than one.

## 2. Schema deviation introduced by this plan

The architecture doc's §5 DDL has no table for refresh tokens, but the auth design in both the architecture doc and the backend build spec requires persisting them (hashed, rotated, revocable by family). `03-database-schema-and-migrations.md` specifies what this table needs to capture. **Action:** once built, this should be folded back into the architecture doc as an addendum so that document stays the actual source of truth for the schema, rather than this plan silently diverging from it.

## 3. Small API-surface gaps noticed while writing the endpoint plan

- ~~A dedicated `DELETE /me`...~~ **Closed.** `DELETE /v1/me` (full account deletion, `app/services/account_service.py`) now exists, distinct from `DELETE /me/data` (reset). Cascades via existing `ON DELETE CASCADE`; an already-issued access token stops working immediately since `get_current_user` re-looks-up the user on every request.
- ~~User-created category creation...~~ **Closed.** `POST /v1/categories` (`CategoryService.create`) lets a user add their own category (name + direction, no `key`).
- ~~User category edit/delete...~~ **Closed.** `PATCH /v1/categories/{id}` and `DELETE /v1/categories/{id}` now exist. Ownership follows the standing convention (09 §3): a system category (`user_id IS NULL`) or another user's is 404-equivalent, never a distinguishable "forbidden." Deleting a category still referenced by a transaction or an overlay's `ovr_category_id` is rejected with the new `category.in_use` (409) code rather than surfacing Postgres's FK error directly.

  Building this delete-guard surfaced a real, pre-existing bug: neither `transactions.category_id` nor `scenario_overlays.ovr_category_id` had an `ON DELETE` rule against `categories` (default RESTRICT). That's harmless for the single-category delete this guard covers, but it made full account deletion (`DELETE /v1/me`) intermittently fail — deleting a user cascades to *both* their categories (`categories.user_id ON DELETE CASCADE`) and their transactions/overlays (via `scenarios` cascading), and Postgres doesn't guarantee which of a table's several cascade paths fires first. Whenever a user had pointed a transaction or an overlay's override at one of their own custom categories, the category's cascade could fire before the transaction/overlay's, hitting the RESTRICT and failing the whole deletion with an unhandled `IntegrityError`. Fixed in migration `0011` by changing both FKs to `ON DELETE SET NULL` (not CASCADE — losing a category should orphan the reference, not delete the row; both columns are already nullable and the app already treats "no category" as normal). Found experimentally, not by inspection: it manifested as stale rows the test-cleanup fixture's `DELETE FROM users` couldn't clear.

## 4. Genuinely unresolved (carried from the architecture and screen-flow docs' own open-questions sections)

These affect the backend directly enough to list here, even though they're really discovery-workshop items:

- **Client's independently-verified test cases** — not yet obtained. A placeholder exists in the golden-fixtures directory; nothing blocks M1 on their absence, but final acceptance depends on getting them and them passing.
- **Password-reset email provider** — who provides/pays for a transactional email service. Blocks moving the stubbed sender in M2 to a real one; doesn't block building the token flow itself.
- ~~**Scenario count cap**~~ **Resolved: 50 plans per account** (`Settings.max_scenarios_per_user`, enforced in `ScenarioService.create`/`duplicate`, counts archived scenarios too; Base is exempt by construction). Product decision, not derived from either locked doc.
- **Export format** — JSON export is planned; whether CSV is also required is open.
- **Accounts, currency display-only confirmation, Hijri dates, Arabic numeral style, notifications in/out** — these mostly affect the client and domain scope rather than backend structure directly, but a change to any of them (e.g. multi-account) would touch the schema and resolver. Tracked here so a "yes" to any of them triggers a plan update before code is written against the old assumption.

## 5. Python version note

This build uses Python 3.14.4 (already set up in the project's `venv/`), rather than the 3.12 the original backend spec assumed. Revisit only if a required dependency doesn't yet support 3.14 — not expected to be an issue, but worth a quick check at the start of M0 rather than discovering it mid-build.

## 6. v1.1 doc alignment (in progress)

The three locked docs were updated to v1.1 after M0–M5 and the Tier 1/2/3 backlog were already built against v1.0. Going through the delta one item at a time, same protocol as the Tier 2 backlog: explain, decide, build or skip, verify, commit.

1. ~~**Rename `opening_balance_*` → Current Cash Balance vocabulary (D-04).**~~ **Done.** `user_settings.opening_balance_minor`/`opening_balance_date` → `current_balance_minor`/`balance_as_of`; `scenarios.opening_balance_override_minor` → `current_balance_override_minor`; the engine's `forecast()` param and `Ledger` field renamed to match. Migration `0012`. Pure rename — no behavior change; every downstream item below builds on this vocabulary.
2. ~~**`PUT /v1/me/balance`** as a dedicated endpoint...~~ **Done.** Split out of `PATCH /me/settings`, which no longer accepts `current_balance_minor`/`balance_as_of` at all (`SettingsService.update_balance()` is now the only code path that writes them). Two new validations: `balance.as_of_in_future` (422) and `balance.as_of_too_old` (422, backstop set at **5 years** — `Settings.balance_as_of_max_age_years`, a product decision like the scenario cap, not derived from either locked doc; distinct from the dashboard's unrelated 30-day stale-balance *prompt*, which is client-side only). Balance immutability (build spec §13.3 #5) is now a genuine Hypothesis property test (`tests/api/test_balance_immutability.py`) driving a random sequence of every other kind of write — scenario, transaction, overlay, category, settings — against one user and asserting the two balance fields never move.
3. **`GET /v1/transactions/{id}/dependents`** — not yet built.
4. **`ScenarioService.duplicate()` doesn't copy overlays** — a real bug against D-13, found while reviewing the v1.1 delta. Not yet fixed.
5. **Archived-scenario guards** (rejected as compare operand / duplicate source, `scenario.not_archived` on a non-archived unarchive) — not yet built.
6. **Scenario cap vs. archived scenarios** — v1.1 §6.2 now says archived scenarios don't count toward the cap; this build's existing, tested behavior is the opposite (Tier 1 #3). Needs a decision before touching it.
7. **Forecast anchor defaults to `balance_as_of`, not today**; horizon accepts any value in range, not just {12,36,60,120}; response gains `current_month`/`months_elapsed` — not yet built.
8. New error codes `balance.as_of_in_future`, `balance.as_of_too_old`, `scenario.archived`, `scenario.not_archived` — land alongside the items that raise them.
9. **M1-numbered fixture reorganization** (`fixtures/m1/`) — blocked on having the actual M1 document, which isn't in this repo; the underlying behavioral tests (balance immutability, partial override, duplicate/archive/restore, dashboard period agreement, currency-change-no-amount-change) are buildable now and don't need to wait on the reorganization itself.
