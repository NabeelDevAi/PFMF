# Open Questions & Future Hardening

Everything here is either deliberately deferred (a scope decision made in this planning pass) or genuinely unresolved (waiting on a client/discovery answer). None of it blocks starting M0/M1.

## 1. Deliberately deferred in this build (see `11-build-order-and-milestones.md`, M6)

- `mypy --strict` on the engine module.
- `import-linter` — engine-purity and layering are held by review discipline until this lands.
- Hypothesis property-based fuzzing — the four core invariants are checked via hand-picked cases in the meantime (`10-testing-strategy.md`).
- GitHub Actions CI and coverage gates.
- OpenAPI export/regression check.
- Automated Alembic drift check.
- Docker packaging and any deployment story — not designed at all yet; this plan only covers local development.
- The in-memory rate limiter — fine for one local process, not fine the moment there's more than one.

## 2. Schema deviation introduced by this plan

The architecture doc's §5 DDL has no table for refresh tokens, but the auth design in both the architecture doc and the backend build spec requires persisting them (hashed, rotated, revocable by family). `03-database-schema-and-migrations.md` specifies what this table needs to capture. **Action:** once built, this should be folded back into the architecture doc as an addendum so that document stays the actual source of truth for the schema, rather than this plan silently diverging from it.

## 3. Small API-surface gaps noticed while writing the endpoint plan

- ~~A dedicated `DELETE /me`...~~ **Closed.** `DELETE /v1/me` (full account deletion, `app/services/account_service.py`) now exists, distinct from `DELETE /me/data` (reset). Cascades via existing `ON DELETE CASCADE`; an already-issued access token stops working immediately since `get_current_user` re-looks-up the user on every request. User category edit/delete are still not built — only create.
- ~~User-created category creation...~~ **Closed.** `POST /v1/categories` (`CategoryService.create`) lets a user add their own category (name + direction, no `key`). Edit/delete of a user category are still not built — only what was explicitly scoped (creation).

## 4. Genuinely unresolved (carried from the architecture and screen-flow docs' own open-questions sections)

These affect the backend directly enough to list here, even though they're really discovery-workshop items:

- **Client's independently-verified test cases** — not yet obtained. A placeholder exists in the golden-fixtures directory; nothing blocks M1 on their absence, but final acceptance depends on getting them and them passing.
- **Password-reset email provider** — who provides/pays for a transactional email service. Blocks moving the stubbed sender in M2 to a real one; doesn't block building the token flow itself.
- ~~**Scenario count cap**~~ **Resolved: 50 plans per account** (`Settings.max_scenarios_per_user`, enforced in `ScenarioService.create`/`duplicate`, counts archived scenarios too; Base is exempt by construction). Product decision, not derived from either locked doc.
- **Export format** — JSON export is planned; whether CSV is also required is open.
- **Accounts, currency display-only confirmation, Hijri dates, Arabic numeral style, notifications in/out** — these mostly affect the client and domain scope rather than backend structure directly, but a change to any of them (e.g. multi-account) would touch the schema and resolver. Tracked here so a "yes" to any of them triggers a plan update before code is written against the old assumption.

## 5. Python version note

This build uses Python 3.14.4 (already set up in the project's `venv/`), rather than the 3.12 the original backend spec assumed. Revisit only if a required dependency doesn't yet support 3.14 — not expected to be an issue, but worth a quick check at the start of M0 rather than discovering it mid-build.
