# Phase 1 — Backend Build Specification

**Status:** Draft v1.0 — internal engineering document
**Owner:** Nabeel Sohail (Technical Lead / Architect)
**Depends on:** `phase1-system-architecture.md` (schema §5, resolution §6, engine §7, compare §8, API §9)
**Audience:** Backend engineers. Sections §11 and §16 are also the Flutter developer's contract.

---

## 1. How to read this

The architecture document says *what* the system is. This says *how we build it* — repo layout, module boundaries, the engine implementation, migrations, testing scaffolding, CI, and the order of work.

Two rules govern everything below.

**The engine is sacred.** `app/engine/` imports nothing from the rest of the codebase. No SQLAlchemy, no FastAPI, no config, no clock. It takes value objects and returns value objects. This is enforced mechanically in CI (§4.2), not by discipline. Every claim we make to the client about testability and reconciliation rests on this one boundary holding.

**Build the engine first, before any API exists.** It carries all the acceptance risk, needs zero infrastructure, and can be validated against the client's own test cases while the app is still wireframes. Sequencing is in §15.

---

## 2. Stack

| Layer | Choice | Notes |
|---|---|---|
| Language | Python 3.12 | |
| Framework | FastAPI | Generates the OpenAPI contract the Flutter client is built from |
| ORM | SQLAlchemy 2.x (typed, async) | |
| Migrations | Alembic | |
| Validation | Pydantic v2 | |
| DB | PostgreSQL 16 | |
| Auth | Argon2id + PyJWT | `argon2-cffi` |
| Tests | pytest, pytest-asyncio, Hypothesis, testcontainers | |
| Lint / format | Ruff | |
| Types | mypy — strict on `engine/`, standard elsewhere | |
| Boundaries | import-linter | Enforces §4.2 |
| Server | Uvicorn behind Gunicorn | |
| Packaging | Docker, multi-stage | |
| CI/CD | GitHub Actions | |

Dependency management: `uv` with a committed lockfile. Pinned, reproducible builds — no floating versions in a financial product.

---

## 3. Repository layout

```
backend/
├── app/
│   ├── engine/                 ★ PURE. No I/O, no framework, no clock.
│   │   ├── types.py            YearMonth, Money, Direction, Recurrence
│   │   ├── models.py           ResolvedTransaction, Occurrence, Ledger, MonthRow
│   │   ├── calendar.py         days_in_month, add_months, clamped dates
│   │   ├── expand.py           recurrence → occurrences
│   │   ├── assumptions.py      Phase 2 seam. No-op in Phase 1.
│   │   ├── forecast.py         the pipeline
│   │   └── compare.py          deltas + drivers
│   │
│   ├── domain/                 enums and value objects shared app-wide
│   ├── db/
│   │   ├── base.py
│   │   ├── session.py
│   │   └── models/             SQLAlchemy ORM models
│   ├── repositories/           all SQL lives here, always user-scoped
│   ├── services/
│   │   ├── scenario_resolver.py   ORM rows → ResolvedTransaction list
│   │   ├── forecast_service.py    load → resolve → engine → DTO
│   │   ├── compare_service.py
│   │   ├── scenario_service.py
│   │   ├── transaction_service.py
│   │   └── auth_service.py
│   ├── api/
│   │   ├── deps.py             auth, db session, current user
│   │   ├── errors.py           error envelope + code registry
│   │   ├── schemas/            Pydantic request/response models
│   │   └── v1/                 routers
│   ├── core/                   config, security, logging
│   └── main.py
│
├── alembic/
├── tests/
│   ├── engine/
│   │   ├── fixtures/           golden JSON cases — including the client's
│   │   ├── test_expand.py
│   │   ├── test_forecast.py
│   │   ├── test_compare.py
│   │   └── test_properties.py  Hypothesis
│   ├── services/
│   ├── api/
│   └── conftest.py
├── scripts/
├── pyproject.toml
├── docker-compose.yml
└── Dockerfile
```

---

## 4. Layering

### 4.1 Direction of dependency

```
api ──→ services ──→ repositories ──→ db
          │
          └────────→ engine          (engine depends on nothing)
```

- **Repositories** hold all SQL. Every query filters on `user_id`. No exceptions, no "internal" helper that skips it.
- **Services** orchestrate. They load data, convert to engine value objects, call the engine, convert results to DTOs.
- **API** handles HTTP, auth and validation only. No business logic in routers.
- **Engine** knows nothing about any of the above.

### 4.2 Enforced in CI

`.importlinter`:

```ini
[importlinter]
root_package = app

[importlinter:contract:engine-is-pure]
name = Engine imports nothing outside itself
type = forbidden
source_modules = app.engine
forbidden_modules =
    app.api
    app.db
    app.services
    app.repositories
    app.core
    sqlalchemy
    fastapi
    pydantic

[importlinter:contract:layers]
name = Layered architecture
type = layers
layers =
    app.api
    app.services
    app.repositories
    app.db
```

If someone imports SQLAlchemy into the engine to "just quickly load a category," the build fails. That is the point.

---

## 5. Configuration

Pydantic `BaseSettings`, environment-driven. Nothing secret in the repo or the image.

```python
class Settings(BaseSettings):
    environment: Literal["local", "staging", "production"]
    database_url: PostgresDsn
    jwt_secret: SecretStr
    jwt_access_ttl_minutes: int = 15
    jwt_refresh_ttl_days: int = 30
    cors_origins: list[str] = []
    log_level: str = "INFO"
    max_horizon_months: int = 120
    max_transactions_per_scenario: int = 500
```

Local: `.env` (gitignored, with a committed `.env.example`). Staging/production: AWS SSM Parameter Store or Secrets Manager, injected at runtime. The app fails fast on startup if a required setting is missing — never a silent default in production.

---

## 6. Engine — types

```python
# app/engine/types.py
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from enum import Enum

Minor = int  # money is ALWAYS integer minor units. Never float. Never Decimal.


class Direction(str, Enum):
    INCOME = "income"
    EXPENSE = "expense"


class Recurrence(str, Enum):
    ONE_TIME   = "one_time"
    WEEKLY     = "weekly"
    BIWEEKLY   = "biweekly"
    MONTHLY    = "monthly"
    QUARTERLY  = "quarterly"
    SEMIANNUAL = "semiannual"
    ANNUAL     = "annual"


class Origin(str, Enum):
    OWN         = "own"          # Base's own transactions
    INHERITED   = "inherited"
    OVERRIDDEN  = "overridden"
    ADDED       = "added"


@dataclass(frozen=True, order=True)
class YearMonth:
    year: int
    month: int

    @classmethod
    def from_date(cls, d: date) -> YearMonth:
        return cls(d.year, d.month)

    @classmethod
    def parse(cls, s: str) -> YearMonth:          # "2026-09"
        y, m = s.split("-")
        return cls(int(y), int(m))

    def add(self, months: int) -> YearMonth:
        idx = self.year * 12 + (self.month - 1) + months
        return YearMonth(idx // 12, idx % 12 + 1)

    def months_until(self, other: YearMonth) -> int:
        return (other.year * 12 + other.month) - (self.year * 12 + self.month)

    def first_day(self) -> date:
        return date(self.year, self.month, 1)

    def __str__(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"
```

`YearMonth` is ordered and hashable, so it works as a dict key and sorts naturally. All month keys crossing the API boundary are `str(YearMonth)`.

```python
# app/engine/models.py
@dataclass(frozen=True)
class ResolvedTransaction:
    id: str
    source_id: str            # base txn id if inherited/overridden, else own id
    origin: Origin
    name: str
    amount_minor: Minor       # always positive
    direction: Direction
    category_id: str | None
    recurrence: Recurrence
    start_date: date
    end_date: date | None


@dataclass(frozen=True)
class Occurrence:
    transaction_id: str
    source_id: str
    origin: Origin
    name: str
    on: date
    amount_minor: Minor
    direction: Direction

    @property
    def signed_minor(self) -> Minor:
        return self.amount_minor if self.direction is Direction.INCOME else -self.amount_minor


@dataclass(frozen=True)
class MonthRow:
    month: YearMonth
    income_minor: Minor
    expense_minor: Minor
    net_minor: Minor
    closing_balance_minor: Minor


@dataclass(frozen=True)
class Ledger:
    anchor_month: YearMonth
    horizon_months: int
    opening_balance_minor: Minor
    months: tuple[MonthRow, ...]
    occurrences: tuple[Occurrence, ...]   # retained for breakdown + drivers
```

Keeping `occurrences` on the `Ledger` is deliberate: it powers the month-breakdown sheet (D2) and the compare drivers list without a second pass or a second query.

---

## 7. Engine — recurrence expansion

The highest-risk code in the product. Written test-first.

```python
# app/engine/calendar.py
from calendar import monthrange
from datetime import date
from .types import YearMonth


def days_in_month(ym: YearMonth) -> int:
    return monthrange(ym.year, ym.month)[1]


def clamped_date(ym: YearMonth, anchor_day: int) -> date:
    """Anchor day clamped into the target month. Jan 31 -> Feb 28/29."""
    return date(ym.year, ym.month, min(anchor_day, days_in_month(ym)))
```

```python
# app/engine/expand.py
from datetime import date, timedelta
from typing import Iterator

from .calendar import clamped_date
from .models import Occurrence, ResolvedTransaction
from .types import Recurrence, YearMonth

DAY_INTERVALS   = {Recurrence.WEEKLY: 7, Recurrence.BIWEEKLY: 14}
MONTH_INTERVALS = {
    Recurrence.MONTHLY: 1,
    Recurrence.QUARTERLY: 3,
    Recurrence.SEMIANNUAL: 6,
    Recurrence.ANNUAL: 12,
}


def expand(txn: ResolvedTransaction, window_start: date, window_end: date) -> Iterator[Occurrence]:
    """Every occurrence of `txn` inside [window_start, window_end], inclusive."""

    if txn.recurrence is Recurrence.ONE_TIME:
        if window_start <= txn.start_date <= window_end:
            yield _occ(txn, txn.start_date)
        return

    hard_end = min(txn.end_date, window_end) if txn.end_date else window_end
    if txn.start_date > hard_end:
        return

    if txn.recurrence in DAY_INTERVALS:
        yield from _expand_day_based(txn, window_start, hard_end)
    else:
        yield from _expand_month_based(txn, window_start, hard_end)


def _expand_day_based(txn, window_start: date, hard_end: date) -> Iterator[Occurrence]:
    step = DAY_INTERVALS[txn.recurrence]

    # Skip straight to the first occurrence at or after the window.
    current = txn.start_date
    if current < window_start:
        gap = (window_start - current).days
        current += timedelta(days=((gap + step - 1) // step) * step)

    while current <= hard_end:
        yield _occ(txn, current)
        current += timedelta(days=step)


def _expand_month_based(txn, window_start: date, hard_end: date) -> Iterator[Occurrence]:
    interval   = MONTH_INTERVALS[txn.recurrence]
    anchor_day = txn.start_date.day
    start_ym   = YearMonth.from_date(txn.start_date)

    # Fast-forward, then step back one interval so a clamped boundary
    # occurrence is never skipped. The window filter below is authoritative.
    n = 0
    if txn.start_date < window_start:
        months_gap = start_ym.months_until(YearMonth.from_date(window_start))
        n = max(0, (months_gap // interval) - 1)

    while True:
        occurrence_date = clamped_date(start_ym.add(n * interval), anchor_day)
        if occurrence_date > hard_end:
            return
        if occurrence_date >= window_start and occurrence_date >= txn.start_date:
            yield _occ(txn, occurrence_date)
        n += 1


def _occ(txn: ResolvedTransaction, on: date) -> Occurrence:
    return Occurrence(
        transaction_id=txn.id, source_id=txn.source_id, origin=txn.origin,
        name=txn.name, on=on, amount_minor=txn.amount_minor, direction=txn.direction,
    )
```

**The clamp rule, restated because it is the bug that will otherwise ship:** `anchor_day` always comes from `txn.start_date`, never from the previously generated occurrence. Jan 31 monthly produces 31 / 28 / 31 / 30 / 31. An implementation that walks forward from the last date produces 31 / 28 / 28 / 28 and drifts permanently. There is a named test for this.

---

## 8. Engine — the pipeline

```python
# app/engine/forecast.py
from collections import defaultdict
from datetime import timedelta

from .assumptions import Assumptions, apply_assumptions
from .expand import expand
from .models import Ledger, MonthRow, Occurrence, ResolvedTransaction
from .types import Direction, Minor, YearMonth


def forecast(
    *,
    opening_balance_minor: Minor,
    anchor_month: YearMonth,
    horizon_months: int,
    transactions: list[ResolvedTransaction],
    assumptions: Assumptions = Assumptions.none(),
) -> Ledger:
    """Pure. Same inputs -> identical output. No I/O, no clock, no randomness."""

    window_start = anchor_month.first_day()
    window_end   = anchor_month.add(horizon_months).first_day() - timedelta(days=1)

    # 1. EXPAND
    occurrences: list[Occurrence] = []
    for txn in transactions:
        occurrences.extend(expand(txn, window_start, window_end))

    # 2. ASSUME — no-op in Phase 1; Phase 2 growth/inflation hooks here
    occurrences = apply_assumptions(occurrences, assumptions)

    # Stable ordering: date, then transaction id. Sums don't depend on it,
    # but the breakdown sheet and any audit output must be reproducible.
    occurrences.sort(key=lambda o: (o.on, o.transaction_id))

    # 3. BUCKET
    buckets: dict[YearMonth, list[Minor]] = defaultdict(lambda: [0, 0])
    for occ in occurrences:
        slot = buckets[YearMonth.from_date(occ.on)]
        if occ.direction is Direction.INCOME:
            slot[0] += occ.amount_minor
        else:
            slot[1] += occ.amount_minor

    # 4. ACCUMULATE
    rows: list[MonthRow] = []
    balance = opening_balance_minor
    for i in range(horizon_months):
        ym = anchor_month.add(i)
        income, expense = buckets.get(ym, (0, 0))
        net = income - expense
        balance += net
        rows.append(MonthRow(ym, income, expense, net, balance))

    return Ledger(
        anchor_month=anchor_month,
        horizon_months=horizon_months,
        opening_balance_minor=opening_balance_minor,
        months=tuple(rows),
        occurrences=tuple(occurrences),
    )
```

```python
# app/engine/assumptions.py — Phase 2 seam, deliberately inert
@dataclass(frozen=True)
class Assumptions:
    @classmethod
    def none(cls) -> "Assumptions":
        return cls()


def apply_assumptions(occurrences, assumptions):
    return occurrences
```

The seam ships in Phase 1 doing nothing. That is intentional: the signature the client is quoted on is the signature Phase 2 extends, so "no engine rebuild" is a verifiable claim rather than a promise.

---

## 9. Engine — compare

```python
# app/engine/compare.py
def compare(a: Ledger, b: Ledger) -> Comparison:
    assert a.anchor_month == b.anchor_month
    assert a.horizon_months == b.horizon_months

    deltas = [
        MonthDelta(
            month=rb.month,
            net_delta_minor=rb.net_minor - ra.net_minor,
            closing_balance_delta_minor=rb.closing_balance_minor - ra.closing_balance_minor,
            closing_balance_delta_pct=_pct(ra.closing_balance_minor, rb.closing_balance_minor),
        )
        for ra, rb in zip(a.months, b.months, strict=True)
    ]
    return Comparison(deltas=tuple(deltas), drivers=_drivers(a, b))


def _pct(base: int, other: int) -> float | None:
    if base == 0:
        return None                       # UI renders "—", never 0% or infinity
    return round((other - base) / abs(base) * 100, 2)
```

`_drivers` totals each `source_id`'s signed occurrences in both ledgers and reports the difference, tagged by how it changed (added / removed / modified / unchanged). Unchanged entries are dropped. The completeness invariant — driver contributions sum exactly to the final closing-balance delta — is a property test (§13.3), and it is what makes the "What's driving this" screen trustworthy rather than decorative.

---

## 10. Persistence

DDL is in architecture §5 and is authoritative. Implementation notes:

- **Alembic autogenerate is a starting point, never the commit.** Every migration is read and edited by hand. CI fails if models and migrations have drifted (§14).
- **Seed system categories in a data migration**, not application startup. They carry `user_id = NULL` and a stable `key`; the Flutter app translates by key.
- **Money columns are `BIGINT`.** Never `NUMERIC`, never `FLOAT`.
- **Date columns are `DATE`.** `TIMESTAMPTZ` appears only on audit fields (`created_at`, `updated_at`), never on anything the engine reads.
- **Deleting a Base transaction cascades** its overlays via `ON DELETE CASCADE` — the row is gone, so overrides and exclusions of it are meaningless.
- **Base plan protection** lives in the service layer: `is_base` scenarios cannot be deleted, archived, or created a second time (the partial unique index backs this up at the DB level).

### 10.1 Scenario resolution

Implements architecture §6. Lives in `services/scenario_resolver.py`, and it is the one service with heavy unit test coverage because it is the bridge between messy persistence and the pure engine.

Two queries, never N+1: one for the scenario's own transactions, one for Base's transactions joined to this scenario's overlays. Resolution then happens in memory.

```python
async def resolve(self, scenario: Scenario) -> list[ResolvedTransaction]:
    if scenario.is_base:
        rows = await self.txn_repo.list_by_scenario(scenario.id)
        return [to_resolved(r, Origin.OWN, source_id=r.id) for r in rows]

    base      = await self.scenario_repo.get_base(scenario.user_id)
    base_rows = await self.txn_repo.list_by_scenario(base.id)
    overlays  = {o.base_transaction_id: o for o in
                 await self.overlay_repo.list_by_scenario(scenario.id)}

    out = []
    for row in base_rows:
        ov = overlays.get(row.id)
        if ov is None:
            out.append(to_resolved(row, Origin.INHERITED, source_id=row.id))
        elif ov.op is OverlayOp.EXCLUDE:
            continue
        else:
            out.append(to_resolved(apply_patch(row, ov), Origin.OVERRIDDEN, source_id=row.id))

    for row in await self.txn_repo.list_by_scenario(scenario.id):
        out.append(to_resolved(row, Origin.ADDED, source_id=row.id))

    return out
```

`apply_patch` takes each `ovr_*` field when non-NULL, otherwise the Base value, and honours `unset_end_date` to force `end_date = None`.

---

## 11. API layer

### 11.1 Error envelope

Every non-2xx response has the same shape. The server never sends display text — the client owns all user-facing language (architecture §10).

```json
{
  "error": {
    "code": "transaction.end_before_start",
    "params": { "field": "end_date" },
    "request_id": "01J8ZQ..."
  }
}
```

### 11.2 Error code registry

This table is part of the Flutter developer's contract. Every code needs an `ar` and `en` string in the app. **Adding a code without telling mobile ships an untranslated error**, so new codes go through a PR that updates this table.

| Code | HTTP | Meaning |
|---|---|---|
| `auth.invalid_credentials` | 401 | Email or password wrong |
| `auth.email_taken` | 409 | Registration with an existing email |
| `auth.token_expired` | 401 | Access token expired — client refreshes |
| `auth.token_invalid` | 401 | Malformed or revoked |
| `auth.weak_password` | 422 | Below policy |
| `validation.required` | 422 | Missing field |
| `validation.invalid` | 422 | Generic field failure |
| `transaction.amount_not_positive` | 422 | Amount ≤ 0 |
| `transaction.end_before_start` | 422 | End date precedes start |
| `transaction.one_time_has_end_date` | 422 | One-time with an end date |
| `transaction.direction_immutable` | 422 | Attempt to change income ↔ expense |
| `transaction.limit_reached` | 422 | Per-scenario cap |
| `scenario.base_immutable` | 409 | Delete/archive of Base |
| `scenario.name_taken` | 409 | Duplicate name for this user |
| `scenario.limit_reached` | 422 | Plan cap |
| `overlay.target_not_in_base` | 422 | Overlay targets a non-Base transaction |
| `overlay.already_exists` | 409 | Duplicate overlay for the same target |
| `compare.same_scenario` | 422 | A and B identical |
| `forecast.invalid_horizon` | 422 | Not 12 / 36 / 60 / 120 |
| `resource.not_found` | 404 | Also returned for another user's resource |
| `rate_limited` | 429 | |
| `internal` | 500 | |

`resource.not_found` for a resource belonging to another user is deliberate. A 403 would confirm the resource exists.

### 11.3 Response conventions

- Money: integer minor units, field names suffixed `_minor`.
- Months: `"YYYY-MM"`. Dates: `"YYYY-MM-DD"`. No timestamps in financial payloads.
- Currency code returned as a separate ISO field, never as a symbol or a formatted string.
- Lists return `{"items": [...]}`, never a bare array, so pagination can be added without a breaking change.
- Every response carries `X-Request-Id`.

### 11.4 Forecast endpoint

```
GET /v1/scenarios/{id}/forecast?horizon=60&anchor=2026-09
```

`horizon` ∈ {12, 36, 60, 120}. `anchor` is optional and defaults to the current month **resolved in the API layer, not the engine** — the engine never reads a clock. Accepting an explicit anchor is what lets QA and the client reproduce any forecast exactly, and it costs nothing.

This one endpoint feeds the Dashboard, all three Forecast chart views, the monthly table and the month breakdown (screen spec §5.1, §7). There is no separate dashboard or chart endpoint, by design.

---

## 12. Auth

- Argon2id via `argon2-cffi`, default parameters, tuned to ~100ms on the production instance size.
- Access token: JWT, 15 min, carries `sub` (user id) and `jti`.
- Refresh token: opaque random, stored **hashed** in the DB, rotated on every use. Reuse of a consumed refresh token revokes the whole family — standard replay defence.
- Rate limits: 5/min on login and register per IP, 3/hour on password reset per email.
- Password reset needs a transactional email provider. **This is an unresolved dependency** — not in the RFP, flagged in screen spec §14 question 5. Until the provider is confirmed, build the token flow and stub the sender behind an interface.
- Logout revokes the refresh family. Access tokens are short enough not to need a blocklist.

---

## 13. Testing

### 13.1 Golden fixtures

Every engine case is a JSON file, so cases can be written by anyone — including the client.

```jsonc
// tests/engine/fixtures/monthly_clamps_to_month_end.json
{
  "name": "Monthly starting Jan 31 clamps in short months",
  "opening_balance_minor": 0,
  "anchor_month": "2026-01",
  "horizon_months": 5,
  "transactions": [
    { "id": "t1", "name": "Rent", "amount_minor": 300000, "direction": "expense",
      "recurrence": "monthly", "start_date": "2026-01-31", "end_date": null }
  ],
  "expected_months": [
    { "month": "2026-01", "income_minor": 0, "expense_minor": 300000,
      "net_minor": -300000, "closing_balance_minor": -300000 },
    { "month": "2026-02", "income_minor": 0, "expense_minor": 300000,
      "net_minor": -300000, "closing_balance_minor": -600000 }
    // ... Mar 31, Apr 30, May 31
  ]
}
```

Loaded by a parametrised test that discovers every file in the directory. Adding a case is adding a file — no code.

**Action for discovery:** RFP §10 requires comparison results to match the client's *independently verified test cases*. We ask for them in the workshop, convert them into this format, and commit them under `fixtures/client/`. Final acceptance then becomes a green CI run instead of a meeting.

### 13.2 Named edge cases

Each of these is its own test with a descriptive name. From architecture §12.2:

`monthly_clamps_to_month_end` · `annual_on_feb_29_in_non_leap_year` · `weekly_across_five_payday_month` · `end_date_before_first_occurrence_yields_nothing` · `end_date_on_occurrence_date_is_inclusive` · `one_time_before_window_excluded` · `one_time_after_window_excluded` · `transaction_starting_before_anchor_contributes_from_anchor` · `empty_scenario_produces_flat_ledger` · `weekly_over_120_months_performance` · `unset_end_date_overlay_makes_open_ended`

### 13.3 Property tests (Hypothesis)

```python
@given(txns=transaction_sets(), opening=st.integers(-10**9, 10**9))
def test_ledger_reconciles(txns, opening):
    ledger = forecast(opening_balance_minor=opening, anchor_month=YearMonth(2026, 1),
                      horizon_months=60, transactions=txns)
    assert ledger.months[-1].closing_balance_minor == \
        opening + sum(o.signed_minor for o in ledger.occurrences)
```

Four invariants:

1. **Reconciliation** — final balance equals opening plus the signed sum of all occurrences. This is RFP §10's core criterion, mechanised.
2. **Isolation** — arbitrary overlays on scenario B never change scenario A's ledger.
3. **Determinism** — identical inputs produce identical output across runs.
4. **Driver completeness** — driver contributions sum exactly to the closing-balance delta.

### 13.4 Layers and gates

| Layer | Scope | Infrastructure |
|---|---|---|
| Engine unit | fixtures, edge cases, properties | none |
| Service | resolution, overlay patching, Base protection | testcontainers Postgres |
| API | auth, ownership, validation, error codes | testcontainers Postgres |
| Contract | OpenAPI schema regression | none |

Coverage gates in CI: **100% branch coverage on `app/engine/`**, ≥85% overall. The engine is held to a higher bar than the CRUD because it is what the client's acceptance criteria actually test.

---

## 14. CI/CD

On every PR:

1. `ruff check` + `ruff format --check`
2. `mypy` — strict on `app/engine/`
3. `lint-imports` — the §4.2 boundary contracts
4. `pytest` with coverage gates
5. **Migration drift check** — `alembic upgrade head`, then autogenerate and fail if a non-empty diff appears
6. **OpenAPI export** — generate `openapi.json`, fail if it changed without the spec being committed

On merge to `main`: build image, push, migrate and deploy to staging, publish `openapi.json` as a build artifact for the Flutter developer.

Production deploy is manual approval, same artifact.

---

## 15. Build order

Six sprints. The sequencing argument matters as much as the list: the engine ships before anything can call it, because it is the only part that can fail acceptance.

| # | Sprint | Delivers | Done when |
|---|---|---|---|
| **0** | Foundation | Repo, Docker, CI skeleton, import contracts, config, health check | CI green on an empty app |
| **1** | **Engine** | types, calendar, expand, forecast, compare, full fixture + property suite | 100% branch coverage on `engine/`; every §13.2 case named and passing; **no API exists yet** |
| **2** | Auth & identity | register, login, refresh, logout, settings, password reset (stubbed sender) | Full auth API tested; rate limits live |
| **3** | Scenarios & transactions | scenario CRUD, Base protection, duplicate/archive, transaction CRUD, categories seeded | Base cannot be deleted; ownership enforced on every route |
| **4** | Overlays & resolution | overlay create/patch/delete, resolver, resolved list with `origin` | Isolation property test passes against the real DB |
| **5** | Forecast & compare API | forecast endpoint, compare endpoint, drivers | Client fixtures pass end-to-end through HTTP |
| **6** | Hardening | export, reset, delete account, logging, perf pass, deploy docs, handover | Staging stable; OpenAPI published; docs complete |

**Sprint 1 is the one to protect.** Every instinct on a client project says start with login screens so there is something to demo. Resist it. The engine is where this project is won or lost, it needs no infrastructure, and finishing it early means the client's own test cases can be run against it while the designer is still in Figma.

### Definition of done, per endpoint

Implemented · unit + integration tested · ownership enforced · errors use registry codes · OpenAPI accurate · error codes communicated to mobile · migration reviewed by hand · CI green.

---

## 16. Handoff to the Flutter developer

The contract is the generated OpenAPI spec plus three things that are not in it:

1. **The error code table (§11.2)** — every code needs `ar` and `en` strings in the app.
2. **The overlay editing semantics** (architecture §9.2, screen spec §4.4). Editing a transaction with `origin = inherited` creates an **overlay**; it does not PATCH the Base transaction. This is the one place a mobile-side misunderstanding silently corrupts the user's real plan.
3. **Formatting is the client's job.** The server sends integer minor units, ISO month keys and a currency code. It never sends a formatted amount, a month name or a user-facing sentence.

Provided by us:
- Published `openapi.json` on every merge to `main`
- Staging base URL + a seeded demo account with a Base plan, two scenarios and a realistic transaction set
- Postman/HTTP collection for the core flows

---

## 17. Conventions

- Trunk-based: short branches off `main`, squash merge.
- Conventional commits (`feat:`, `fix:`, `refactor:`, `test:`, `chore:`).
- Every PR states what it changes and how it was tested. PRs touching `app/engine/` need a second reviewer.
- Migrations are never edited after merge — always a new migration forward.
- No `TODO` in `main` without a linked issue.
- Type hints everywhere. `Any` in the engine fails review.
