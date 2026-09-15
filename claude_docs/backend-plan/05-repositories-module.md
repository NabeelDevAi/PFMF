# Repositories Module

## 1. Purpose

Every SQL statement in the entire backend lives here, and nowhere else. Services never issue a query directly; they call a repository method. This is what makes "every query is scoped by `user_id`" an auditable claim rather than a hope — there is exactly one place to check.

## 2. Repositories this build needs

| Repository | Backs | Notes |
|---|---|---|
| `UserRepository` | `users` | Lookup by id and by email (for login/registration); email uniqueness check. |
| `UserSettingsRepository` | `user_settings` | One row per user; read and patch (currency, locale, Current Cash Balance + as-of date). |
| `CategoryRepository` | `categories` | Reads system categories (user_id NULL) plus a given user's own categories together; user categories are created/owned per user. |
| `ScenarioRepository` | `scenarios` | CRUD scoped by user; a dedicated lookup for "the Base scenario for this user" (used constantly by the resolver); enforces at the query level that archived scenarios are excluded unless asked for. |
| `TransactionRepository` | `transactions` | CRUD scoped by user *and* by scenario; a method to list all of a given scenario's own rows (used both for Base's transactions and for a derived scenario's own additions). |
| `OverlayRepository` | `scenario_overlays` | CRUD scoped by scenario; a method to list every overlay for a scenario keyed by the Base transaction it targets (this is exactly the shape the resolver needs, so the repository hands it back pre-indexed rather than making the service do that). |
| `RefreshTokenRepository` | the new refresh-tokens table (see `03-database-schema-and-migrations.md`) | Create, look up by hash, mark used/rotated, and revoke an entire token family. |

## 3. Rules every repository follows

- Every method that touches a specific user's data takes a `user_id` and includes it in the `WHERE` clause — no method exists that can be called without one, and no "internal" helper is exempt.
- A resource that exists but belongs to a different user is treated identically to a resource that doesn't exist at all (repositories return "not found," and the API layer turns that into the same 404-equivalent response either way — this is a deliberate security property, not an oversight, and is explained further in `09-auth-and-security.md`).
- No repository method returns more than one query's worth of data if it can be avoided — the overlay lookup above is written the way it is specifically to avoid the resolver needing to issue one query per base transaction (N+1).
- Repositories return data, not decisions — validation and business rules (e.g. "Base cannot be deleted") live in services, not here. A repository will delete a row if asked; a service decides whether asking was allowed.

## 4. Testing plan

Repository tests run against the dedicated local test database (see `02-configuration-and-environment.md`), not against fakes — the whole point of this layer is real SQL behavior (constraints, cascades, the partial unique index), so tests need a real Postgres underneath them. Each repository's tests cover its basic CRUD plus, explicitly, a cross-user isolation case: a query scoped to user A must never be able to see or affect user B's row, even if given B's id by mistake somewhere upstream. That isolation check is treated as a first-class test category here, not an afterthought bundled into a CRUD test.
