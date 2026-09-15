# Phase 1 — Backend Build Specification

**Status:** v1.1 — aligned to signed M1
**Authority:** `Milestone 1 — Discovery & Specification v1.1` Part 2 (rules R1–R35, cases 18.1–29.4). Where this document and M1 disagree, M1 wins.

**Changes in v1.1:** engine signature takes `current_balance_minor` (D-04) · duplicate, archive and dependents service logic (§10.2–§10.4) · new error codes (§11.2) · forecast anchor comes from `balance_as_of`, plus `current_month` / `months_elapsed` in the response (§11.4) · fixture format and named cases updated to the M1 register (§13) · build order revised (§15).
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
    current_balance_minor: Minor      # user-confirmed (D-04), never system-mutated
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
    current_balance_minor: Minor,     # from user_settings; never mutated by the system
    anchor_month: YearMonth,          # from user_settings.balance_as_of
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
    balance = current_balance_minor
    for i in range(horizon_months):
        ym = anchor_month.add(i)
        income, expense = buckets.get(ym, (0, 0))
        net = income - expense
        balance += net
        rows.append(MonthRow(ym, income, expense, net, balance))

    return Ledger(
        anchor_month=anchor_month,
        horizon_months=horizon_months,
        current_balance_minor=current_balance_minor,
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
- **`current_balance_minor` and `balance_as_of` are written by exactly one service method**, called from exactly one endpoint (`PUT /v1/me/balance`). No other code path touches them — not transaction writes, not scenario writes, not a scheduled job. There are no scheduled jobs. D-04 is a hard constraint from a signed rule (M1 R1), and §13.3 asserts it as a property test rather than trusting review to catch a violation.

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

**Field-level resolution is contractual (M1 R19).** The override is a sparse patch, resolved against live Base values at read time. Never widen this into a whole-row copy, a JSONB snapshot, or an "eager materialise on write" optimisation: M1 case 25.11 pins the numbers at 310,400, and a snapshot produces 312,900. That difference is a defect inside Phase 1 scope.

### 10.2 Duplicate

```python
async def duplicate(self, source: Scenario) -> Scenario:
    target = await self.scenario_repo.create(
        user_id=source.user_id,
        name=await self._unique_name(source.user_id, f"{source.name} (copy)"),
        is_base=False,
        current_balance_override_minor=source.current_balance_override_minor,
    )
    if not source.is_base:
        await self.overlay_repo.copy_all(from_=source.id, to=target.id)   # new ids
        await self.txn_repo.copy_all(from_=source.id, to=target.id)       # new ids
    # Base source: copy nothing. Inheritance alone reproduces it (M1 25.16).
    return target
```

Two traps, both with named tests. Copying rows when the source **is** Base doubles every item. Copying the **resolved** set instead of the overlay set severs inheritance, so M1 case 25.15 step 3 fails — the duplicate stops tracking a Base salary change.

Rejected sources: archived scenarios (restore first). The duplicate is a sibling, never a child — no parent column exists, deliberately.

### 10.3 Archive

`archived_at = now()` / `NULL`. Service rules: Base cannot be archived; archived scenarios are excluded from the default list, rejected as a comparison operand, rejected as a duplicate source, and excluded from any scenario cap. Nothing else changes, so overlays keep resolving against live Base rows and a restore picks up every intervening Base change (M1 R23, case 25.17).

### 10.4 Base transaction deletion and dependents

`ON DELETE CASCADE` removes overlays targeting a deleted Base transaction (M1 R20, cases 25.12–25.14).

`GET /v1/transactions/{id}/dependents` returns the count and names of scenarios holding an overlay on that row, so the client can warn before deleting:

```python
async def dependents(self, txn_id: UUID, user_id: UUID) -> list[ScenarioRef]:
    return await self.overlay_repo.scenarios_referencing(txn_id, user_id)
```

One indexed query on `scenario_overlays.base_transaction_id`. Deletion is never blocked — it is the user's own financial picture — but it must not be silent.

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
| `balance.as_of_in_future` | 422 | As-of date later than today |
| `balance.as_of_too_old` | 422 | As-of date beyond the supported backstop |
| `scenario.archived` | 409 | Archived scenario used as active, compare operand or duplicate source |
| `scenario.not_archived` | 409 | Unarchive on a scenario that is not archived |
| `scenario.base_not_duplicable_with_rows` | 500 | Internal guard: Base duplicate attempted to copy rows (M1 25.16) |
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

`horizon` is measured in months **from the anchor**. `anchor` is optional and defaults to the month of `user_settings.balance_as_of` — resolved in the API layer, never in the engine, which reads no clock. Accepting an explicit anchor is what lets QA and the client reproduce any forecast exactly, and it costs nothing.

**The anchor is the as-of month, which may be in the past.** If a user confirmed their balance five months ago, the ledger starts five months ago and a 12-month horizon only reaches seven months past today. The response therefore carries two fields the client needs and must not compute itself from a device clock:

```jsonc
{
  "anchor_month": "2026-01",
  "balance_as_of": "2026-01-01",
  "current_balance_minor": 4500000,
  "current_month": "2026-06",     // where today sits in `months`
  "months_elapsed": 5,            // anchor -> current, in months
  "horizon_months": 17,
  // ...
}
```

A dashboard wanting twelve months ahead of today requests `months_elapsed + 12`. `months_elapsed` also drives the stale-balance prompt threshold.

Validation: `horizon` between 1 and `max_horizon_months`; the four client-facing values are 12, 36, 60 and 120, but the endpoint accepts any value in range because the dashboard needs `months_elapsed + 12`. Rejecting anything outside the four would break the dashboard the moment a balance goes stale.

This one endpoint feeds the Dashboard, all three Forecast chart views, the monthly table and the month breakdown (screen spec §5.1, §7). There is no separate dashboard or chart endpoint, by design. Dashboard period totals are a client-side sum of the monthly rows in this payload — the only arithmetic the client performs, permitted because summing the server's own integers cannot disagree with the server.

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
  "current_balance_minor": 0,
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

**The M1 register is the fixture directory.** Every case in M1 Part 2 (18.1 through 29.4) exists as a file under `fixtures/m1/`, named by its case number, with the case reference and the rules it verifies in metadata. M1 §33 makes any disagreement between the software and an agreed case a defect inside Phase 1 scope, so these are not documentation we consult — they are tests that gate every merge. The traceability table promised in M1 §9.2 is generated from that metadata, so it cannot drift from what actually runs.

**Still outstanding from the client:** their own independently verified cases, to be committed under `fixtures/client/` in the same format (M1 §30). Final acceptance is then a green CI run rather than a meeting.

### 13.2 Named edge cases

Each of these is its own test with a descriptive name. From architecture §12.2:

`monthly_clamps_to_month_end` (M1 22.1) · `annual_on_feb_29_in_non_leap_year` (23.2) · `monthly_on_31st_through_leap_february` (23.1) · `weekly_across_five_payday_month` (24.1) · `end_date_before_first_occurrence_yields_nothing` · `end_date_on_occurrence_date_is_inclusive` (21.1) · `end_date_one_day_before_occurrence_excludes_it` (21.2) · `one_time_before_window_excluded` (19.2) · `one_time_after_window_excluded` (19.3) · `transaction_starting_before_anchor_contributes_from_anchor` (20.3) · `empty_scenario_produces_flat_ledger` (18.1) · `weekly_over_120_months_performance` · `unset_end_date_overlay_makes_open_ended`

Added in v1.1, from the agreed M1 cases:

`scheduled_occurrence_does_not_change_current_balance` (18.3) · `balance_update_reanchors_ledger` (18.4) · `stale_anchor_reports_months_elapsed` (18.5) · `override_of_one_field_follows_base_on_others` (**25.11 — the most important new case**) · `base_delete_cascades_to_overriding_scenario` (25.13) · `base_delete_cascades_to_excluding_scenario` (25.14) · `duplicate_keeps_live_base_inheritance` (25.15) · `duplicate_is_independent_of_source` (25.15 step 4) · `duplicate_of_base_yields_each_item_once` (25.16) · `archive_restore_reflects_current_base` (25.17) · `dashboard_period_windows_agree_with_forecast` (27.3) · `currency_change_alters_no_amount` (28.1)

### 13.3 Property tests (Hypothesis)

```python
@given(txns=transaction_sets(), balance=st.integers(-10**9, 10**9))
def test_ledger_reconciles(txns, balance):
    ledger = forecast(current_balance_minor=balance, anchor_month=YearMonth(2026, 1),
                      horizon_months=60, transactions=txns)
    assert ledger.months[-1].closing_balance_minor == \
        balance + sum(o.signed_minor for o in ledger.occurrences)
```

Six invariants:

1. **Reconciliation** — final balance equals the Current Cash Balance plus the signed sum of all occurrences. RFP §10's core criterion, mechanised (M1 check 29.1).
2. **Isolation** — arbitrary overlays on scenario B never change scenario A's ledger (M1 check 29.3).
3. **Determinism** — identical inputs produce identical output across runs (M1 check 29.2).
4. **Driver completeness** — driver contributions sum exactly to the closing-balance delta (M1 check 29.4).
5. **Balance immutability** (new in v1.1) — drive arbitrary sequences of transaction, overlay, scenario and settings writes against a real database and assert that `current_balance_minor` and `balance_as_of` are untouched by everything except `PUT /v1/me/balance`. D-04 rests on a signed rule, so it is asserted rather than reviewed for.
6. **Partial override** (new in v1.1) — for a scenario overriding an arbitrary subset of fields, changing any non-overridden field in Base changes the resolved value, and changing an overridden field does not. The general form of M1 case 25.11.

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
| **1** | **Engine** | types, calendar, expand, forecast, compare, full fixture + property suite | 100% branch coverage on `engine/`; every §13.2 case named and passing; every M1 engine-level case in `fixtures/m1/`; **no API exists yet** |
| **2** | Auth & identity | register, login, refresh, logout, settings, `PUT /me/balance`, password reset (stubbed sender) | Full auth API tested; rate limits live; balance-immutability property test green |
| **3** | Scenarios & transactions | scenario CRUD, Base protection, duplicate (§10.2), archive/restore (§10.3), transaction CRUD, dependents (§10.4), categories seeded | Base cannot be deleted or archived; M1 25.16 and 25.17 pass; ownership enforced on every route |
| **4** | Overlays & resolution | overlay create/patch/delete, resolver, resolved list with `origin` and per-field override metadata | Isolation and partial-override property tests pass against the real DB; **M1 25.11 passes** |
| **5** | Forecast & compare API | forecast endpoint with `current_month` / `months_elapsed`, compare endpoint, drivers | Every M1 case passes end-to-end through HTTP, including 27.3 |
| **6** | Hardening | export, reset, delete account, logging, perf pass, deploy docs, handover | Staging stable; OpenAPI published; docs complete |

**Sprint 1 is the one to protect.** Every instinct on a client project says start with login screens so there is something to demo. Resist it. The engine is where this project is won or lost, it needs no infrastructure, and finishing it early means the M1 cases — and the client's own, when they arrive — can be run against it while the designer is still in Figma.

**Sprint 4 is the one to review hardest.** M1 case 25.11 lives there, and it is the only case in the register where a plausible, tidy-looking implementation produces a confidently wrong number. Every PR touching `scenario_resolver.py` or the overlay schema needs two reviewers.

### Definition of done, per endpoint

Implemented · unit + integration tested · ownership enforced · errors use registry codes · OpenAPI accurate · error codes communicated to mobile · migration reviewed by hand · CI green.

---

## 16. Handoff to the Flutter developer

The contract is the generated OpenAPI spec plus three things that are not in it:

1. **The error code table (§11.2)** — every code needs `ar` and `en` strings in the app.
2. **The overlay editing semantics** (architecture §9.2, screen spec §4.4). Editing a transaction with `origin = inherited` creates an **overlay**; it does not PATCH the Base transaction. This is the one place a mobile-side misunderstanding silently corrupts the user's real plan.
3. **Send only changed fields on an overlay PATCH.** Echoing the whole resolved row back converts a partial override into a snapshot and breaks M1 R19 from the client side, even against a correct backend. M1 case 25.11 is the acceptance test and it fails on a client that echoes.
4. **The Current Cash Balance is written only by `PUT /v1/me/balance`**, only from explicit user action. The client never derives it, adjusts it after a transaction write, or updates it optimistically on resume. It is displayed with `balance_as_of` and never as a bare figure.
5. **`current_month` and `months_elapsed` come from the forecast response, not the device clock.** They position "today" within the ledger, drive the dashboard period window, and decide the stale-balance prompt.
6. **Check dependents before deleting a Base transaction** — `GET /v1/transactions/{id}/dependents`, then the warning copy in screen spec §6.4.
7. **Formatting is the client's job.** The server sends integer minor units, ISO month keys and a currency code. It never sends a formatted amount, a month name or a user-facing sentence.

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
