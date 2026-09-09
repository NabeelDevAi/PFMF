# Repo Layout & Conventions

## 1. Directory structure

| Path | Contents / purpose |
|---|---|
| `backend/app/engine/` | The pure forecasting engine. No imports from anywhere else in the app, no SQLAlchemy, no FastAPI, no clock. |
| `backend/app/domain/` | Shared enums and plain value objects used across API/services/repositories (e.g. the direction, recurrence, overlay-op vocabulary as it appears outside the engine). |
| `backend/app/db/` | SQLAlchemy setup: engine/session factory, declarative base, and the ORM models themselves. |
| `backend/app/repositories/` | All SQL. One repository per aggregate (users, settings, categories, scenarios, transactions, overlays, refresh tokens). Every method that touches user data takes a `user_id` and filters by it. |
| `backend/app/services/` | Orchestration. Loads via repositories, converts to/from engine value objects, enforces business rules, returns data ready to become an API response. |
| `backend/app/api/` | FastAPI routers, dependencies (auth, DB session, current user), Pydantic request/response schemas, and the error code registry. HTTP concerns only — no business logic here. |
| `backend/app/core/` | Configuration, security primitives (hashing, JWT), logging setup. |
| `backend/app/main.py` | App instantiation, router registration, startup checks. |
| `backend/alembic/` | Migrations. |
| `backend/tests/engine/` | Engine unit tests: golden fixtures, named edge cases, invariant checks. No infrastructure needed. |
| `backend/tests/repositories/`, `backend/tests/services/`, `backend/tests/api/` | Tests requiring the local test database. |
| `backend/scripts/` | One-off operational scripts (e.g. local test DB setup/teardown, seed data). |

No `docker-compose.yml` / `Dockerfile` for now — deployment packaging is out of scope until we reach it (tracked in `12-open-questions-and-future-hardening.md`).

## 2. Dependency direction (unchanged from the original spec)

`api` depends on `services`. `services` depends on `repositories` and on `engine`. `repositories` depends on `db`. `engine` depends on nothing in this list.

This is enforced by code review discipline for now (no `import-linter` yet — see `12-open-questions-and-future-hardening.md`). The rule to hold the line on: if you find yourself importing SQLAlchemy, FastAPI, or Pydantic inside `app/engine/`, stop — the value belongs in a service, and the engine should receive a plain value instead.

## 3. Naming conventions

- Module and file names: `snake_case`, one aggregate/concern per file (mirrors the original spec's `expand.py`, `forecast.py`, `compare.py` split inside the engine).
- One repository class per aggregate root: `UserRepository`, `ScenarioRepository`, `TransactionRepository`, `OverlayRepository`, `RefreshTokenRepository`, `CategoryRepository`.
- One service per capability, not per table: `ScenarioResolver`, `ForecastService`, `CompareService`, `AuthService`, `ScenarioService`, `TransactionService`, `OverlayService`, `SettingsService`. (A service is allowed to use more than one repository.)
- Test files mirror the module they test (`tests/engine/test_expand.py` tests `app/engine/expand.py`).
- Engine test fixture files are named for the behavior they prove (e.g. `monthly_clamps_to_month_end`), not for a ticket number.

## 4. Coding conventions

- Type hints everywhere. `Any` inside `app/engine/` is a rejected pattern even before we have mypy enforcing it mechanically.
- Money is always an integer (minor units) at every layer, from the database column up through the API response. It is never a float and never a `Decimal` — even transiently.
- Dates cross every internal boundary as `date`, never `datetime`, except audit columns (`created_at`/`updated_at`), which are the only place a timestamp belongs.
- Docstrings on every engine function stating its contract in the same terms as the architecture doc (pure, no I/O, boundary inclusivity) — the engine's documentation is part of what makes it auditable to the client, not just to us.

## 5. Git & PR conventions

- Trunk-based: short-lived branches off `main`, squash merge.
- Conventional commit prefixes (`feat:`, `fix:`, `refactor:`, `test:`, `chore:`).
- Any change touching `app/engine/` gets read twice before merging (self-review pass, since this is a solo build) — treat it with the same suspicion the original spec asks a second human reviewer to bring.
- Migrations are additive only — a mistake in an already-merged migration is fixed with a new migration, never by editing history.
