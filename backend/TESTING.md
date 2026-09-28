# Running the test suite

How to reproduce the test environment from scratch: exact dependency
versions plus the one piece of infrastructure the suite needs (a local
Postgres database). See `claude_docs/backend-plan/02-configuration-and-environment.md`
and `claude_docs/backend-plan/10-testing-strategy.md` for the design
reasoning behind this setup; this doc is just the commands.

## 1. Requirements

- Python 3.12+
- PostgreSQL 18, reachable locally, with a role that can connect and create
  extensions on the test database (see step 3 — migration `0001` runs
  `CREATE EXTENSION IF NOT EXISTS citext`, which needs that privilege).

## 2. Install exact dependency versions

`requirements-lock.txt` pins the entire toolchain — runtime and test/dev
(pytest, mypy, ruff, hypothesis, import-linter, httpx) — to the exact
versions last known to work together. Install from it, not
`requirements.txt`/`requirements-dev.txt` (those are loosely-constrained
source-of-intent files, not what to install from for a reproducible run):

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements-lock.txt
```

## 3. Create the test database

One **dedicated** database, separate from whatever dev database you may
also have — the suite truncates it between tests, so it must never be one
you're using for anything else.

```bash
createdb -U postgres pfmf_test
```

(Or: `psql -U postgres -c "CREATE DATABASE pfmf_test;"`. `-U postgres`
matches `.env.example`'s default local setup — a superuser role connected
to over the unix socket. Substitute whatever role/host you actually use;
any connection method works as long as that role can create the `citext`
extension on the database, which migration `0001` does automatically.)

No manual schema/migration step is needed beyond creating the empty
database: the test suite runs `alembic upgrade head` against it itself,
automatically, once per test session.

## 4. Point the suite at it

Copy `.env.example` to `.env` if you don't already have one, and set:

```bash
TEST_DATABASE_URL=postgresql+psycopg://<role>@<host>/pfmf_test
```

(`DATABASE_URL` also has to be set and valid, even though the test suite
itself only uses `TEST_DATABASE_URL` — the app fails fast on missing
config at import time. Point it at any reachable Postgres database, e.g.
a local `pfmf_dev`.)

## 5. Run it

```bash
pytest
```

That's the whole suite — engine (no DB), repository/service/API
(real Postgres), rate limiting, everything. First run will apply
migrations to `pfmf_test`; subsequent runs reuse the same schema and just
reset data between tests.

Lint/type-check, run the same way CI would eventually run them:

```bash
ruff check .
ruff format --check .
mypy            # scoped to app/engine only, see pyproject.toml
lint-imports    # import-linter; enforces the layering contracts in pyproject.toml
```
