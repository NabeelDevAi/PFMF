# Configuration & Environment

## 1. Approach

Settings are environment-driven (Pydantic `BaseSettings` at implementation time), sourced from a local `.env` file that is gitignored, with a `.env.example` committed so the required shape is documented. The app fails fast on startup if a required setting is missing — no silent defaults for anything security- or correctness-sensitive.

## 2. Settings this build needs

| Setting | Purpose | Local default posture |
|---|---|---|
| `environment` | `local` / `staging` / `production` switch | `local` |
| `database_url` | Connection string to the local Postgres instance | Points at a dedicated dev database on the existing local Postgres 18 server |
| `test_database_url` | Connection string used only by the test suite | Points at a **separate** dedicated test database on the same local server — never the dev database |
| `jwt_secret` | Signs access tokens | A generated local-only secret, never committed |
| `jwt_access_ttl_minutes` | Access token lifetime | 15 (per architecture) |
| `jwt_refresh_ttl_days` | Refresh token lifetime | 30 (per architecture) |
| `cors_origins` | Allowed origins for the Flutter dev client | Local dev origins only for now |
| `log_level` | Logging verbosity | `INFO` locally, adjustable |
| `max_horizon_months` | Forecast horizon cap (the request-range validation, not an account-scarcity limit — see below) | 120 |
| `balance_as_of_max_age_years` | Hard backstop on `PUT /me/balance`'s as-of date | 5 |
| `password_reset_sender` | Which email-sending implementation to use | A stub/console sender locally (see `09-auth-and-security.md`) |
| Rate-limit thresholds | Login/register/password-reset limits | As specified in `09-auth-and-security.md` |

**No setting for a scenario or per-scenario transaction cap.** Both existed briefly (`max_scenarios_per_user`, `max_transactions_per_scenario`) and were removed by explicit product decision — no limit on how many plans or transactions an account can hold.

## 3. Local PostgreSQL setup

The machine already has PostgreSQL 18 running locally (confirmed listening on port 5432). This build uses:

- **One dev database** for day-to-day development, migrated with Alembic as the schema evolves.
- **One separate test database**, created once and then managed by the test suite's own fixtures (schema applied via Alembic at the start of a test session, data reset between tests as needed). Keeping it physically separate from the dev database means a bad test run can never corrupt data you're looking at while developing.
- **Local-dev simplification (revisit before any shared/staging environment):** the app connects as the `postgres` superuser itself, authenticated via a local `trust` rule on the unix socket (no password). This is a deliberate simplification for a single-developer machine, not the original plan's dedicated-role-per-app posture — it must not carry over once this runs anywhere other than this machine.

## 4. Secrets handling

Nothing secret is committed to the repo. Locally that means `.env` is gitignored and holds the JWT secret and the local database credentials. When this moves toward staging/production, secrets move to a managed secret store — that migration is out of scope for now and tracked as a deferred item, not solved today.

## 5. What's deliberately not here yet

No Docker Compose file defining a Postgres service — the existing local instance fills that role directly. No cloud-specific configuration (AWS Secrets Manager, SSM) — those only become relevant once we plan an actual deployment, which is out of scope for this build plan.
