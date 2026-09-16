# Database Schema & Migrations

## 1. Source of truth

The DDL in `phase1-system-architecture.md` §5 is authoritative for every table it defines: `users` (including `deleted_at`, §5.4 addendum), `user_settings` (including `avatar_filename`, §5.3 addendum), `categories`, `scenarios`, `transactions`, `scenario_overlays`, `refresh_tokens` (§5.2 addendum), plus the enums `direction`, `recurrence`, `overlay_op`. This plan does not redesign that schema — it only sequences building it and names one addition it's missing.

## 2. The one schema addition this build introduces: refresh tokens

**Resolved — folded back into `phase1-system-architecture.md` §5.2 as an addendum.** The architecture doc's original DDL had no table for refresh tokens, but the auth design (both docs) required one: refresh tokens are opaque, stored **hashed**, rotated on every use, and a reused/already-consumed token must revoke its whole family. That needed persistence — a table wasn't optional here, it was implied by the requirement and simply wasn't drawn.

What it captures (built in migration `0006`, matches the architecture doc's addendum exactly):
- Which user it belongs to.
- A hash of the token value (never the raw value).
- A family/lineage identifier, so revoking one compromised token can revoke every token descended from it.
- Whether it has been used/rotated already (to detect reuse).
- Issued-at and expiry timestamps.
- Ownership scoping applies here exactly like every other table: lookups are always scoped by `user_id`.

## 3. Migration tooling and approach

- **Alembic**, one migration per logical schema change.
- **Autogenerate is a draft, never the commit.** Every migration is read and hand-edited before it's considered done — particularly to double check enum types, the partial unique index enforcing one Base scenario per user, and the category-naming check constraint, none of which autogenerate always expresses cleanly.
- **System categories are seeded via a data migration**, not at application startup — they're data, not runtime behavior, and belong in migration history like any other seed data.
- No automated CI drift check yet (`alembic upgrade head` + autogenerate-diff-must-be-empty) — that's a hardening-phase addition (see `12-open-questions-and-future-hardening.md`). For now, drift is caught by discipline: any model change is immediately followed by a migration in the same piece of work.

## 4. Sequencing of migrations

Roughly in dependency order, matching the build order in `11-build-order-and-milestones.md`:

1. Enum types (`direction`, `recurrence`, `overlay_op`) + `users`.
2. `user_settings`.
3. `categories`, plus the seed-data migration for system categories.
4. `scenarios`, including the partial unique index enforcing one Base plan per user.
5. `transactions`.
6. `scenario_overlays`, including the cascade rule from `transactions` and the uniqueness constraint per (scenario, base transaction).
7. Refresh tokens table (new, described above) — lands alongside the auth milestone (M2), not before, since nothing needs it until then.

## 5. Integrity rules the migrations must actually enforce, not just describe

- Money columns are `BIGINT`. Never `NUMERIC`, never `FLOAT` — this is checked in review of the migration itself, not just the ORM model.
- Date columns are `DATE`; only audit columns (`created_at`, `updated_at`) are `TIMESTAMPTZ`.
- Deleting a Base transaction cascades to any overlays referencing it (`ON DELETE CASCADE`) — an override/exclusion of a transaction that no longer exists is meaningless, so it should simply disappear with it.
- The application layer additionally enforces that a Base scenario can never be deleted or archived — the partial unique index is the database-level backstop for "exactly one Base," not a substitute for that service-layer rule.
