# Personal Financial Forecasting App — Phase 1 System Architecture

**Status:** v1.1 — aligned to signed M1
**Owner:** Nabeel Sohail (Technical Lead / Architect)
**Audience:** Internal engineering + design team, and (edited subset) the client
**Authority:** `Milestone 1 — Discovery & Specification v1.1`, Part 2 (rules R1–R35, cases 18.1–29.4)

**Changes in v1.1** — all from the client's M1 red-team review and the agreed balance model:
Current Cash Balance separated from Projected Balance (D-04, §5, §7) · field-level overlay confirmed as a locked decision (D-11) · archived scenarios keep live inheritance (D-12) · duplicate copies overlays, not the resolved set (D-13) · as-of date is user-level, not per-scenario (D-14) · delete-cascade dependents warning (§6.3, §9) · dashboard selected-period aggregation (§9.1).

---

## 1. Purpose of this document

This document locks the technical foundation for Phase 1 before any screen is designed or any line of app code is written. It defines the domain model, the forecasting engine contract, the database schema, the API surface, and the seams that let Phase 2 be added without a rebuild.

Everything downstream depends on this:

| Downstream artifact | Depends on |
|---|---|
| UI/UX screen inventory & wireframes | §4 domain model, §9 API surface |
| Flutter implementation | §9 API contract, §10 localization rules |
| Backend implementation | §5 schema, §6–7 engine spec, §9 API |
| Client acceptance | §12 test strategy mapped to RFP §10 |

The single most important idea in this document: **the forecast is a pure function.** Everything else in Phase 1 — dashboard, charts, comparison — is a view over its output. If that function is clean, isolated, and testable, the project passes acceptance. If it leaks into the UI or the database, it does not.

**Where this document sits relative to M1.** The signed M1 document is the contractual authority. Its rules R1–R35 and cases 18.1–29.4 define required behaviour; this document defines how we implement it. Where the two appear to disagree, M1 wins and this document is wrong. Every decision in §2 cites the M1 rule it implements, so the trace runs from a signed sentence to a schema column to a test.

---

## 2. Locked architectural decisions

These are decided. Changing any of them after this point is a change-control event, not a discussion.

| # | Decision | Rationale | If wrong, cost |
|---|---|---|---|
| **D-01** | **A scenario is an overlay on the Base Plan, not a snapshot copy.** | RFP §4.4's examples ("Buy House", "Salary Increase") imply the user does not re-enter their whole financial life per scenario. A Base edit must propagate. | High — schema and engine rewrite |
| **D-02** | **Phase 1 is plan-only. No actuals, no marking-as-paid, no bank sync.** | RFP §4 contains no tracking mechanics. "Track" in the vision statement means entering assumptions. | High — second data model |
| **D-03** | **One cash pot per user. No multi-account.** | RFP §3 mentions "accounts" but §4.1–4.8 never define them. Multi-account implies transfers, per-account balances, allocation. | Medium — additive in Phase 2 |
| **D-04** | **Current Cash Balance is user-confirmed and never mutated by the system.** It carries an `as_of` date which anchors the forecast. No scheduled occurrence, and no passage of time, alters it. Projected Balance is a separate, engine-computed figure. | Agreed with the client at M1 (R1–R3). Phase 1 cannot verify actual transactions, so the only balance the app may assert is one the user confirmed. Updating the balance is the Phase 1 substitute for tracking. | High — schema, engine contract, dashboard |
| **D-05** | **Currency is display-only.** One primary currency per user. No FX, no conversion, no multi-currency holdings. | RFP says "SAR and other major currencies" — read as choice of primary, not simultaneous. Stated as an explicit assumption to client. | Medium |
| **D-06** | **The forecast engine is server-side, single implementation.** Flutter renders, never calculates. | Two engines (Dart + Python) produce diverging numbers and fail RFP §10 acceptance. | Critical |
| **D-07** | **No offline mode.** Consequence of D-06. Explicit exclusion in the proposal. | Offline-first with sync conflict resolution can double mobile cost and is not requested. | Medium |
| **D-08** | **Frozen recurrence set:** one-time, weekly, bi-weekly, monthly, quarterly, semi-annual, annual. No custom cron-style rules. | RFP's "other practical schedules" is open-ended and unpriceable. This list covers salary, rent, utilities, subscriptions, loans, bonuses. | Low |
| **D-09** | **Monthly forecast granularity only.** Annual figures are aggregations of monthly, computed client-side from the same payload. | RFP §4.5 names monthly as primary. One granularity, one code path. | Low |
| **D-10** | **All money is stored and computed as integer minor units** (halalas / cents). Floats never touch a financial value. | Float arithmetic produces non-reconciling balances over 120 months. Non-negotiable. | Critical |
| **D-11** | **An overlay records changed fields only, never a whole-item snapshot.** Fields the scenario did not override continue to resolve from Base at read time. | M1 R19, case 25.11. A snapshot would freeze a plan's rent at the old amount permanently, with nothing on screen to indicate staleness. | High — the defect case 25.11 exists to catch exactly this |
| **D-12** | **An archived scenario keeps its live Base inheritance.** Archiving sets `archived_at` and nothing else; restoring reflects Base as it stands at restore time. | M1 R23, case 25.17. Freezing at archive time would need a snapshot, contradicting D-01 and D-11. | Low — additive flag |
| **D-13** | **Duplicating a scenario copies its overlays and its own transactions, and gives the copy an independent live link to Base.** It never flattens the resolved set, and never creates a parent link to the source. | M1 R24–R26, cases 25.15–25.16. Duplicating Base must yield an empty-overlay scenario, not copies of every Base row. | Medium — service logic, easy to get subtly wrong |
| **D-14** | **`balance_as_of` is user-level, never per-scenario.** A scenario may override the balance *amount* but not the date. | Every scenario therefore shares one forecast anchor, which is what makes comparison well-defined (M1 R27, and the assertion in §8). | Medium — comparison correctness |

---

## 3. System context & components

```
┌──────────────────────────────────────────────┐
│  Flutter App (iOS / Android)                 │
│  • Presentation + local UI state only        │
│  • i18n (ar/en), RTL/LTR layout              │
│  • Charts rendered from server ledger        │
│  • ZERO financial calculation                │
└───────────────────┬──────────────────────────┘
                    │ HTTPS / JSON / JWT
┌───────────────────▼──────────────────────────┐
│  FastAPI Backend                             │
│  ┌────────────────────────────────────────┐  │
│  │ API Layer (routing, authz, validation) │  │
│  ├────────────────────────────────────────┤  │
│  │ Application Services                   │  │
│  │  scenario resolution, orchestration    │  │
│  ├────────────────────────────────────────┤  │
│  │ ★ FORECAST ENGINE (pure, no I/O)       │  │
│  │   expand → assume → bucket → accumulate│  │
│  ├────────────────────────────────────────┤  │
│  │ Repository Layer (SQLAlchemy)          │  │
│  └────────────────────────────────────────┘  │
└───────────────────┬──────────────────────────┘
                    │
┌───────────────────▼──────────────────────────┐
│  PostgreSQL (RDS) — encrypted at rest        │
└──────────────────────────────────────────────┘
```

**The engine boundary is the most important line in this diagram.** The engine module imports no database code, no framework code, no clock. It receives plain value objects and returns plain value objects. This is what makes RFP §10's "independently testable" and "reconcile to the transaction model" achievable rather than aspirational.

---

## 4. Domain model

**User** — identity and auth.
**UserSettings** — currency, locale, the Current Cash Balance and the date the user confirmed it (`balance_as_of`). The as-of date is user-level, never per-scenario (D-14), so every scenario shares one forecast anchor.
**Scenario** — a named set of financial assumptions. Exactly one per user has `is_base = true`.
**Transaction** — a recurring or one-time money movement *definition*. Not an event that happened.
**Occurrence** — a single dated instance generated from a Transaction. Computed, never stored.
**ScenarioOverlay** — an instruction to exclude or modify a Base transaction within a derived scenario.
**Ledger** — the engine's output: an ordered list of monthly rows.

Vocabulary note for the whole team: a *transaction* here is a rule, not a record of something that happened. When the client says "transaction" they mean the same thing. When Phase 2 adds real tracking, those become *actuals* and get a different table and a different word.

---

## 5. Data model

Money: `BIGINT` minor units, always positive. Direction is a separate column — never encode expenses as negative amounts, because sign-flipping bugs are the most common source of non-reconciling ledgers.

Dates: `DATE` only. No timestamps, no timezones, anywhere in the financial model. A salary on the 25th is on the 25th regardless of where the phone is.

```sql
CREATE TYPE direction      AS ENUM ('income', 'expense');
CREATE TYPE recurrence     AS ENUM ('one_time','weekly','biweekly','monthly',
                                    'quarterly','semiannual','annual');
CREATE TYPE overlay_op     AS ENUM ('exclude', 'override');

CREATE TABLE users (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email          CITEXT UNIQUE NOT NULL,
  password_hash  TEXT NOT NULL,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE user_settings (
  user_id                 UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  display_name            TEXT,
  currency_code           CHAR(3) NOT NULL DEFAULT 'SAR',
  locale                  TEXT    NOT NULL DEFAULT 'en',   -- 'en' | 'ar'
  -- Current Cash Balance (D-04): user-confirmed, never mutated by the system.
  -- No scheduled occurrence and no scheduled job may write these two columns.
  current_balance_minor   BIGINT  NOT NULL DEFAULT 0,
  balance_as_of           DATE    NOT NULL,   -- anchors every forecast (D-14)
  updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- System categories have user_id NULL and are translated client-side by `key`.
-- User categories carry free-text `name` stored as entered.
CREATE TABLE categories (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    UUID REFERENCES users(id) ON DELETE CASCADE,
  key        TEXT,            -- e.g. 'salary','rent','utilities' (system only)
  name       TEXT,            -- user-defined only
  direction  direction NOT NULL,
  sort_order INT NOT NULL DEFAULT 0,
  CONSTRAINT category_naming CHECK (
    (user_id IS NULL AND key IS NOT NULL AND name IS NULL) OR
    (user_id IS NOT NULL AND name IS NOT NULL AND key IS NULL)
  )
);

CREATE TABLE scenarios (
  id                             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id                        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name                           TEXT NOT NULL,
  is_base                        BOOLEAN NOT NULL DEFAULT FALSE,
  current_balance_override_minor BIGINT,        -- NULL = inherit from user_settings.
                                                -- Amount only: the as-of date is
                                                -- user-level and not overridable (D-14)
  archived_at                    TIMESTAMPTZ,
  created_at                     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at                     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX one_base_per_user
  ON scenarios(user_id) WHERE is_base;

CREATE TABLE transactions (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  scenario_id   UUID NOT NULL REFERENCES scenarios(id) ON DELETE CASCADE,
  name          TEXT NOT NULL,
  amount_minor  BIGINT NOT NULL CHECK (amount_minor > 0),
  direction     direction NOT NULL,
  category_id   UUID REFERENCES categories(id),
  notes         TEXT,
  recurrence    recurrence NOT NULL,
  start_date    DATE NOT NULL,
  end_date      DATE,                            -- NULL = open-ended
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT valid_range CHECK (end_date IS NULL OR end_date >= start_date),
  CONSTRAINT one_time_has_no_end CHECK (recurrence <> 'one_time' OR end_date IS NULL)
);
CREATE INDEX txn_by_scenario ON transactions(scenario_id);

-- Overlay = how a derived scenario modifies an inherited Base transaction.
-- Typed nullable columns (not JSONB) so overrides stay queryable and validated.
-- `unset_end_date` solves the NULL-vs-not-overridden ambiguity for the one
-- nullable overridable field.
CREATE TABLE scenario_overlays (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  scenario_id          UUID NOT NULL REFERENCES scenarios(id) ON DELETE CASCADE,
  base_transaction_id  UUID NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
  op                   overlay_op NOT NULL,

  ovr_name          TEXT,
  ovr_amount_minor  BIGINT CHECK (ovr_amount_minor IS NULL OR ovr_amount_minor > 0),
  ovr_category_id   UUID REFERENCES categories(id),
  ovr_recurrence    recurrence,
  ovr_start_date    DATE,
  ovr_end_date      DATE,
  unset_end_date    BOOLEAN NOT NULL DEFAULT FALSE,

  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (scenario_id, base_transaction_id)
);
```

**Direction is deliberately not overridable.** Turning an income into an expense is semantically a different transaction; the user should exclude and add. This removes a whole class of confusing comparison output.

### 5.1 Why Base is itself a scenario

The Base Plan is a row in `scenarios` with `is_base = true`. Its transactions live in `transactions` with `scenario_id` pointing at it. This means:

- One code path resolves every scenario. Base just happens to have zero overlays.
- Base can never be deleted or archived (enforced in the service layer).
- Overlays only ever target Base transactions in Phase 1 — scenarios do not chain off other scenarios. Flat hierarchy, one level deep.
- **Duplicating** copies overlay rows and scenario-local transaction rows, with fresh ids. No parent link is created, so source and duplicate are siblings (D-13). Duplicating Base produces a scenario with **zero** overlays and **zero** own transactions — it inherits everything. Copying Base's rows as scenario-local would double every item; case 25.16 exists to catch that.
- **Archiving** sets `archived_at` and touches nothing else (D-12). The scenario's overlays continue to resolve against live Base rows, so a restore picks up every Base change made while it was away.

### 5.2 Addendum: refresh tokens

Not part of this document's original DDL above — added post-build, once the auth design (§ tokens) was actually implemented, per `backend-plan/03-database-schema-and-migrations.md` §2. Folded back in here so this document stays the actual source of truth for the schema, rather than the backend plan silently diverging from it. Matches migration `0006` exactly.

```sql
CREATE TABLE refresh_tokens (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  family_id   UUID NOT NULL,   -- lineage: revoking one revokes every token
                                -- descended from the same login
  token_hash  TEXT NOT NULL UNIQUE,   -- never the raw token value
  used_at     TIMESTAMPTZ,     -- set on rotation; reuse after this is set
                                -- is the theft signal that revokes the family
  revoked_at  TIMESTAMPTZ,
  expires_at  TIMESTAMPTZ NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX ix_refresh_tokens_family_id ON refresh_tokens(family_id);
CREATE INDEX ix_refresh_tokens_token_hash ON refresh_tokens(token_hash);
```

Note: migration `0014` (Phase 1 §11 item 8 — removing the forgot/reset-password-via-email flow) drops the unrelated `password_reset_tokens` table, which was never part of this document's schema to begin with; `refresh_tokens` above is unaffected by that change.

---

## 6. Scenario resolution

Before the engine runs, the application layer resolves a scenario into a flat, plain list of transaction definitions.

```
resolve(scenario) -> List[ResolvedTransaction]

  if scenario.is_base:
      return scenario.own_transactions

  base     = base_scenario_of(scenario.user_id)
  overlays = index_by_base_txn_id(scenario.overlays)
  out      = []

  for txn in base.transactions:
      ov = overlays.get(txn.id)
      if ov is None:
          out.append(as_resolved(txn, origin=INHERITED, source_id=txn.id))
      elif ov.op == EXCLUDE:
          continue
      else:                                    # OVERRIDE
          out.append(as_resolved(apply_patch(txn, ov),
                                 origin=OVERRIDDEN, source_id=txn.id))

  for txn in scenario.own_transactions:        # scenario-local additions
      out.append(as_resolved(txn, origin=ADDED, source_id=txn.id))

  return out
```

`apply_patch` takes each `ovr_*` field when non-NULL, otherwise the Base value. `unset_end_date = true` forces `end_date = NULL` (makes an ending transaction open-ended).

**This field-level resolution is a contractual behaviour, not an implementation nicety (D-11, M1 R19).** A scenario that overrode only `end_date` must pick up a later Base change to `amount`. M1 case 25.11 pins the numbers: Base rent moves 4,500 → 5,000, and the plan that overrode only the end date must produce 310,400, not 312,900. The second figure means someone snapshotted the row instead of patching fields, and it is a defect within Phase 1 scope. Resist any refactor toward a JSONB blob or a whole-row copy — the nullable typed columns exist precisely to make partial override the path of least resistance.

The `origin` tag is not decoration — it drives the comparison "drivers" feature in §8 and the UI's "inherited from Base / modified / scenario-only" badges, which are the difference between a comparison the user trusts and one they don't.

**Isolation guarantee (RFP §4.4, §10; M1 R17, case 25.8):** derived scenarios hold only overlays and their own rows. No write path in the system mutates Base transactions from a scenario context. This is enforced structurally, not by convention, and it is covered by a property test in §12.

### 6.1 Duplicate

```
duplicate(source) -> Scenario

  target = create_scenario(user_id, name=unique_name(source.name + " (copy)"),
                           is_base=False,
                           current_balance_override_minor=source.current_balance_override_minor)

  if not source.is_base:
      copy_rows(source.overlays        -> target, new_ids=True)
      copy_rows(source.own_transactions -> target, new_ids=True)
  # Base source: nothing copied. Inheritance alone reproduces it.

  return target
```

Two failure modes to guard with tests: copying Base's transactions when the source *is* Base (doubles every item — case 25.16), and copying the *resolved* set instead of the overlay set for a derived source (severs inheritance, so case 25.15 step 3 fails).

### 6.2 Archive

`archived_at = now()` on archive, `NULL` on restore. Service-layer rules: Base cannot be archived; an archived scenario is excluded from the default scenario list, rejected as a comparison operand, and rejected as a duplicate source; archived scenarios do not count toward any scenario cap. If the archived scenario is the client's active context, the API response signals that the client should fall back to Base.

### 6.3 Deleting a Base transaction

Deleting a Base transaction cascades its overlays via `ON DELETE CASCADE` — the override or exclusion of a row that no longer exists is meaningless (M1 R20, cases 25.12–25.14).

Because that silently changes other scenarios, the client must be able to warn first. `GET /v1/transactions/{id}/dependents` returns the count and names of scenarios holding an overlay on it, backed by one indexed query on `scenario_overlays.base_transaction_id`. The confirm dialog copy is in the screen spec §6.4.

Re-adding a transaction with the same name later creates a new row with a new id, so no overlay can attach to it retroactively (M1 R21). This falls out of using surrogate keys and needs no special handling — but it is worth a test, because a "helpful" name-matching restore would violate the rule.

---

## 7. The forecast engine

### 7.1 Contract

```python
def forecast(
    current_balance_minor: int,   # user-confirmed (D-04); never mutated by the system
    anchor_month: YearMonth,      # from user_settings.balance_as_of; never from a clock
    horizon_months: int,          # 12 | 36 | 60 | 120
    transactions: list[ResolvedTransaction],
    assumptions: Assumptions = Assumptions.none(),   # Phase 2 seam, no-op in P1
) -> Ledger
```

Pure. No database, no network, no `date.today()`, no randomness, no mutation of inputs. Same inputs always produce byte-identical output. This is the property that makes it independently testable and lets us hand the client a spreadsheet of expected values that we can prove we match.

**The agreed balance model made this stricter, not looser.** An earlier draft had the dashboard's "current balance" summing occurrences dated on or before today, which would have pulled today's date into a displayed financial figure. Under D-04 the Current Cash Balance is a stored, user-confirmed number and the engine never needs to know what day it is. Today's date is used for exactly two things, both outside the engine: deciding which month the dashboard's period window starts in, and deciding whether to show the stale-balance prompt.

### 7.2 Pipeline

```
transactions
   │
   ├─ 1. EXPAND      → occurrences (dated, signed instances)
   ├─ 2. ASSUME      → no-op in Phase 1 (Phase 2: inflation, salary growth)
   ├─ 3. BUCKET      → group occurrences by YYYY-MM
   └─ 4. ACCUMULATE  → running balance across months
                     → Ledger
```

### 7.3 Stage 1 — Expansion

Window: `[anchor_month_start, anchor_month_start + horizon_months)`.

**One-time:** emits exactly one occurrence on `start_date`, only if it falls inside the window.

**Day-based** (`weekly` = 7d, `biweekly` = 14d):
```
occurrence(n) = start_date + (n × interval_days)
```
Emit while `occurrence(n) <= min(end_date ?? window_end, window_end)`. Months naturally receive 4 or 5 weekly occurrences. We do **not** normalise to a monthly average — the ledger must reconcile to real dates, and a 5-payday month is a real thing users will look for.

**Month-based** (`monthly` = 1, `quarterly` = 3, `semiannual` = 6, `annual` = 12):
```
target        = add_months(start_date_month, n × interval_months)
anchor_day    = day_of_month(start_date)
occurrence(n) = date(target.year, target.month,
                     min(anchor_day, days_in_month(target)))
```

**Clamp, never drift.** The anchor day always comes from the original `start_date`, never from the previously generated occurrence. A rent starting Jan 31 produces: Jan 31 → Feb 28 → Mar 31 → Apr 30 → May 31. A naive implementation that walks forward from the last occurrence produces Mar 28, and the error compounds. This is the single most common bug in recurrence engines and it has an explicit test.

Leap years fall out of `days_in_month` for free: annual on Feb 29 → Feb 28 in non-leap years, Feb 29 when available.

**Boundaries:** `start_date` is inclusive, `end_date` is inclusive. A transaction whose `end_date` precedes its first occurrence emits nothing — valid, not an error.

### 7.4 Stage 3–4 — Bucket and accumulate

```
for each month M in window (in order):
    income   = Σ occurrences in M where direction = income
    expense  = Σ occurrences in M where direction = expense
    net      = income − expense
    closing  = previous_closing + net       # month 0 previous = current_balance
```

All arithmetic on `int`. No division anywhere in Phase 1, therefore no rounding policy needed yet. When Phase 2 introduces growth rates, rounding is defined once, at the assumption stage, as **half-even at the occurrence level** — never at the aggregate level, or the ledger stops reconciling.

### 7.5 Output shape

```jsonc
{
  "scenario_id": "...",
  "anchor_month": "2026-09",
  "balance_as_of": "2026-09-01",
  "current_balance_minor": 4500000,
  "current_month": "2026-09",       // where "today" sits in this ledger
  "months_elapsed": 0,              // anchor_month -> current_month, in months
  "horizon_months": 60,
  "currency_code": "SAR",
  "months": [
    {
      "month": "2026-09",
      "income_minor": 2500000,
      "expense_minor": 1830000,
      "net_minor": 670000,
      "closing_balance_minor": 5170000
    }
    // ... one row per month
  ],
  "totals": {
    "income_minor": 150000000,
    "expense_minor": 109800000,
    "net_minor": 40200000,
    "closing_balance_minor": 44700000
  }
}
```

Note what is absent: no formatted strings, no localised labels, no currency symbols, no percentages of anything. Raw integers and ISO month keys. The client formats. This is what makes Arabic/English a rendering concern rather than a backend concern (§10).

`current_balance_minor` is echoed back so the dashboard can render the Current Cash Balance and the Projected Balance from one payload without a second call, and `balance_as_of` lets it label the figure with its date (M1 R1).

`current_month` and `months_elapsed` exist because the anchor is the as-of month, which may be in the past if the user has not confirmed their balance for a while. The client needs to know where "today" sits in the returned rows: to start its period window there (M1 R33), and to decide whether to show the stale-balance prompt. Without these two fields the client would compute them from its own device clock, which drifts and cannot be tested. `months_elapsed` is also what the client uses to request a long enough horizon — the horizon is counted from the **anchor**, so a dashboard wanting twelve months ahead of today must ask for `months_elapsed + 12`.

### 7.6 Reconciliation invariant

```
closing_balance[last] == current_balance + Σ(signed amounts of ALL occurrences)
```

This holds by construction and is asserted as a property test on randomly generated transaction sets. It is the direct, mechanical answer to RFP §10: *"Forecast calculations reconcile to the transaction/event model."*

### 7.7 Performance

Worst realistic case: 200 transactions, 120-month horizon, weekly recurrence → ~104,000 occurrences. Single-digit milliseconds in Python. **No caching in Phase 1.** A cache is a correctness risk (stale ledgers after edits) for a performance problem we do not have. The engine is a pure function, so a cache keyed on a hash of its inputs can be dropped in later with zero engine changes if profiling ever demands it.

---

## 8. Scenario comparison

Two ledgers, same `anchor_month` and `horizon_months`, aligned by month key.

```jsonc
{
  "a": { /* ledger A */ },
  "b": { /* ledger B */ },
  "deltas": [
    {
      "month": "2027-03",
      "net_delta_minor": -450000,
      "closing_balance_delta_minor": -1350000,
      "closing_balance_delta_pct": -12.4    // null when A's value is 0
    }
  ],
  "drivers": [
    { "origin": "added",      "name": "Mortgage payment", "direction": "expense",
      "total_contribution_minor": -32400000 },
    { "origin": "overridden", "name": "Rent", "direction": "expense",
      "base_total_minor": 21600000, "scenario_total_minor": 0,
      "total_contribution_minor": 21600000 },
    { "origin": "excluded",   "name": "Savings transfer", "direction": "expense",
      "total_contribution_minor": 6000000 }
  ]
}
```

Percentage is `null`, not zero, when the baseline is zero — the UI shows a dash, never "∞%" or a misleading 0%.

**The `drivers` array is the strategically important part.** RFP §4.6 asks us to "clearly communicate which assumptions drive the difference," and RFP §16 asks how we make the engine trustworthy. Drivers are computed by diffing the two resolved transaction sets by `origin` and `source_id`, then summing each one's occurrences inside the window. Contributions sum exactly to the total closing-balance delta — another property test. This turns comparison from a chart the client eyeballs into an auditable explanation.

---

## 9. API surface

REST, JSON, JWT bearer. OpenAPI 3 auto-generated by FastAPI and published to the Flutter developer, who generates a typed client from it. **The OpenAPI spec is the contract between backend and mobile** — no informal endpoint descriptions over WhatsApp.

```
POST   /v1/auth/register
POST   /v1/auth/login
POST   /v1/auth/refresh
POST   /v1/auth/logout

GET    /v1/me
PATCH  /v1/me/settings              currency, locale, display name
PUT    /v1/me/balance               Current Cash Balance + as-of date (D-04)

GET    /v1/categories               system + user categories

GET    /v1/scenarios                ?include_archived=false
POST   /v1/scenarios
GET    /v1/scenarios/{id}
PATCH  /v1/scenarios/{id}           rename, balance-amount override (D-14: amount only)
DELETE /v1/scenarios/{id}           404-equivalent on base
POST   /v1/scenarios/{id}/duplicate
POST   /v1/scenarios/{id}/archive
POST   /v1/scenarios/{id}/unarchive

GET    /v1/scenarios/{id}/transactions      resolved view, each row carries `origin`
POST   /v1/scenarios/{id}/transactions      creates scenario-local (origin=added)
PATCH  /v1/transactions/{id}
DELETE /v1/transactions/{id}
GET    /v1/transactions/{id}/dependents     scenarios holding an overlay on this row (§6.3)

POST   /v1/scenarios/{id}/overlays          exclude or override a base txn
PATCH  /v1/scenarios/{id}/overlays/{ovid}
DELETE /v1/scenarios/{id}/overlays/{ovid}   revert to inherited

GET    /v1/scenarios/{id}/forecast          ?horizon=12|36|60|120&anchor=YYYY-MM
GET    /v1/forecast/compare                 ?a={id}&b={id}&horizon=&anchor=

DELETE /v1/me/data                          reset (RFP §4.8)
GET    /v1/me/export                        JSON export (RFP §4.8)
```

### 9.1 One number, one source

`PUT /v1/me/balance` is deliberately a separate endpoint rather than a field on `PATCH /me/settings`. Amount and as-of date must move together and are the only write in the system that re-anchors every forecast; separating them keeps that consequence visible in the API, the logs and the client code, instead of hidden among currency and locale changes.

There is no `/dashboard` endpoint and no `/charts` endpoint. The dashboard is rendered from the `/forecast` payload, and every chart in RFP §4.7 is rendered from the same payload:

| RFP §4.7 chart | Source |
|---|---|
| Income vs expense | `months[].income_minor` / `expense_minor` |
| Net cash flow | `months[].net_minor` |
| Projected cash balance over time | `months[].closing_balance_minor` |
| Scenario comparison | `/forecast/compare` |
| Monthly & annual summaries | monthly rows; annual = client-side sum of 12 |

If the dashboard had its own query, it would eventually disagree with the forecast, and the client would find it. One payload, one truth.

**Dashboard figures (M1 R32, case 27.3).** Everything on the dashboard comes from one forecast call:

| Dashboard figure | Source | Responds to the period selector? |
|---|---|---|
| Current Cash Balance | `current_balance_minor` + `balance_as_of` | **No** — it is a stored, confirmed figure (R1) |
| Income / Expenses / Net | sum of `months[]` across the window | Yes |
| Projected Balance | `closing_balance_minor` of the window's last month | Yes |
| Outlook indicator | slope of `net_minor` across the window | Yes |
| Stale-balance prompt | `months_elapsed` against the agreed threshold | No |

The window runs from `current_month` forward by 1, 3, 6 or 12 months — never backward (R33), because Phase 1 has no actuals and a past month would be a projection of something already settled.

The period aggregation is a client-side sum of integers the server already sent. This is the one arithmetic the client is permitted, and it is permitted because it cannot disagree with the server: summing the server's own monthly rows is not a second calculation of anything.

### 9.2 Editing semantics the mobile developer must get right

When the user opens a transaction inside a **derived** scenario and edits it:

- `origin = inherited` → this creates an **overlay** (`POST /overlays`), it does **not** PATCH the Base transaction.
- `origin = overridden` → PATCH the existing overlay.
- `origin = added` → PATCH the transaction directly; it belongs to this scenario.

Deleting behaves the same way: deleting an inherited row creates an `exclude` overlay. The UI must show "Remove from this plan" rather than "Delete" in that case. This is the one place where a mobile-side misunderstanding would silently corrupt the Base Plan, so it gets its own section in the API handover doc and its own UAT test case.

**Editing an overridden row sends only the changed fields.** A PATCH on an overlay must carry the fields the user just touched, not a full echo of the resolved row. Sending every field back turns a partial override into a whole-row snapshot and breaks D-11 from the client side, even with a correct backend. Case 25.11 is the acceptance test for this, and it will fail on a client that echoes.

**Three more semantics the client must not improvise:**

- **Balance.** The Current Cash Balance is written only by `PUT /v1/me/balance`, only from explicit user action. The client never derives, adjusts or optimistically updates it — not after adding a transaction, not on a date change, not on app resume.
- **Archive.** `POST /archive` and `/unarchive`. If the archived scenario was the active context, the client falls back to Base. Archived scenarios are excluded from the switcher, the compare picker and the duplicate source list.
- **Delete a Base transaction.** Call `GET /v1/transactions/{id}/dependents` first and show the warning if the count is non-zero (screen spec §6.4). Deleting without checking is silent data loss from the user's other plans.

---

## 10. Localization & RTL architecture

Arabic and English from day one, single build, no code changes to add a third language (RFP §5.1).

**Server rules:**
- Never returns display-formatted text. No `"SAR 4,500.00"`, no `"March 2027"`, no English prose in errors.
- Errors return a machine code plus parameters: `{"code":"txn.end_before_start","params":{"field":"end_date"}}`. The client owns the message.
- System categories return `key`; the client translates. User-created categories return the user's own text, untouched.
- Months are ISO `YYYY-MM`. Amounts are integer minor units. Currency is a separate ISO code field.

**Client rules:**
- Flutter `intl` + ARB files, `ar` and `en`. `MaterialApp` drives direction from locale.
- Use `EdgeInsetsDirectional` / `start`/`end` throughout. Any `left`/`right` in layout code fails review.
- Arabic numerals: use Western Arabic digits (٠١٢ vs 012 is a client decision — flag to client during discovery; Saudi financial apps typically use Western digits, and that is our default assumption).
- **Charts need explicit RTL handling.** Most Flutter chart libraries do not mirror axes automatically. Time axis should read right-to-left in Arabic. This is a known cost item, budgeted in QA, and it is exactly the kind of thing that gets discovered late on projects that treat i18n as a translation task.
- Language selectable at onboarding and in Settings, applied without restart.

**Arabic copy** is provided and reviewed by the client, or quoted as a separate line item. We do not silently absorb translation review for a financial product where a mistranslated label is a liability.

---

## 11. Security

- Passwords: Argon2id.
- Access tokens short-lived (15 min); refresh tokens rotated, revocable, stored hashed.
- Every repository query is scoped by `user_id`. Ownership is checked in the data layer, not only in routing — a missing decorator must not become a data leak.
- TLS 1.2+ in transit; RDS encryption at rest; automated encrypted backups.
- Secrets in AWS Secrets Manager / SSM Parameter Store. Nothing in the repo, nothing in the image (RFP §5).
- Rate limiting on auth endpoints.
- Structured logs with no financial values and no PII. Request IDs only.
- Architecture supports biometric unlock later (RFP §4.1): it is a client-side gate over stored refresh tokens, requiring no backend change.

---

## 12. Testing strategy

This section exists to make RFP §10 mechanical instead of subjective. Each acceptance criterion maps to executable tests.

| RFP §10 criterion | How it is proven |
|---|---|
| Recurring transactions start, repeat and stop correctly | Expansion unit + edge-case suite (§12.2); M1 cases 20.x–24.x |
| One-time transactions land in the correct period | Boundary tests at window edges; M1 cases 19.1–19.3 |
| Forecast reconciles to the transaction model | Reconciliation property test (§7.6); M1 check 29.1 |
| Scenario changes do not alter Base | Isolation property test (§12.3); M1 cases 25.8, 25.9 |
| Comparison matches independently verified test cases | Golden fixtures, including the client's own (§12.1); M1 cases 26.1–26.3 |

**Every M1 case is a committed test.** M1 §33 makes any disagreement between the software and an agreed case a defect inside Phase 1 scope, so the case register is not a document we consult — it is a directory of fixtures that runs in CI. The traceability table promised in M1 §9.2 is generated from test metadata rather than maintained by hand, so it cannot drift from what actually runs.

### 12.1 Golden fixtures

Each case is a JSON file: input transaction set + anchor + horizon + expected ledger. Run as a parametrised suite.

**Action for discovery:** RFP §10 says comparison results must match *"independently verified test cases."* The client has these. We ask for them in the workshop, convert them into this fixture format, and commit them. Acceptance then becomes a green test run instead of an argument in a meeting. This is also a strong differentiator to state in the proposal answer to RFP §16.

### 12.2 Edge-case suite (non-negotiable)

- Monthly starting Jan 31 across a non-leap year → 31/28/31/30/31
- Annual starting Feb 29 → Feb 28 in non-leap years
- Weekly across a 5-payday month
- `end_date` before the first occurrence → zero occurrences
- `end_date` exactly on an occurrence date → included
- One-time before / after the window → excluded
- Transaction starting before the anchor month → contributes only from the anchor forward
- Empty scenario → flat ledger at the Current Cash Balance
- 120-month horizon with weekly recurrence → performance + correctness
- Overlay setting `unset_end_date` on a previously-ending transaction

Added in v1.1, from the agreed M1 cases:

- Scheduled occurrences never alter the stored Current Cash Balance (M1 18.3)
- Re-anchoring: balance updated to a later as-of date rebuilds the ledger from that month, with no earlier month present (M1 18.4)
- Stale anchor: as-of month in the past, `months_elapsed` correct, ledger still anchored to as-of (M1 18.5)
- Field-level override survives a Base change to a different field (M1 25.11) — **the single most important new case**
- Base delete cascades to an overriding scenario and to an excluding scenario (M1 25.13, 25.14)
- Duplicate of a derived scenario keeps live Base inheritance and is independent of its source (M1 25.15)
- Duplicate of Base yields each item exactly once (M1 25.16)
- Archive, Base change, restore → restored ledger reflects the new Base (M1 25.17)
- Dashboard period windows at 1 / 3 / 6 / 12 months agree with the forecast rows (M1 27.3)
- Currency change alters no stored or computed amount (M1 28.1)

### 12.3 Property tests (Hypothesis)

- **Reconciliation:** for any generated transaction set, final balance equals the Current Cash Balance plus the signed sum of occurrences.
- **Isolation:** applying arbitrary overlays to scenario B never changes scenario A's ledger.
- **Determinism:** running the same input twice yields identical output.
- **Driver completeness:** driver contributions sum exactly to the total closing-balance delta.
- **Balance immutability:** no API call other than `PUT /v1/me/balance` changes `current_balance_minor` or `balance_as_of`. Exercised by driving arbitrary sequences of transaction, overlay and scenario writes and asserting both columns are untouched. This is D-04 enforced as a test rather than a convention.
- **Partial override:** for a scenario overriding an arbitrary subset of fields, changing any non-overridden field in Base changes the resolved value; changing an overridden field does not. The general form of case 25.11.

### 12.4 Layers

Unit (engine, no I/O) → integration (API + DB via testcontainers) → contract (OpenAPI schema regression) → UAT (client, bilingual). CI on GitHub Actions: lint, type-check, full test suite, coverage gate on the engine module specifically — the engine is held to a higher bar than the CRUD.

---

## 13. Deployment

Docker images, single FastAPI service, RDS PostgreSQL, Alembic migrations run as a pre-deploy step. GitHub Actions for build/test/deploy. Staging and production environments. Monthly operating cost estimate is produced from the finalised instance sizing and given to the client as a separate line (RFP §6, §11).

---

## 14. Phase 2 extension seams

RFP §16 asks directly: *"How would you structure the architecture so Phase 2 can be added without rebuilding Phase 1?"* This section is the answer, and it should be summarised in the proposal.

**The core idea: everything compiles down to occurrences.** The engine consumes a stream of dated, signed amounts. It does not care what produced them.

| Phase 2 feature (RFP §7) | Seam | Engine change |
|---|---|---|
| **Financial events** — house, car, loan, travel | An event *compiler* expands one event into ordinary transaction definitions: down payment (one-time) + loan payment (monthly) + insurance (annual). It emits into the same resolved list. | **None** |
| **What-if analysis** | A what-if is an ephemeral scenario built from an event compiler, forecast, compared, and discarded or saved. Existing endpoints. | **None** |
| **Best / expected / worst case** | The `Assumptions` parameter (§7.1, already in the signature, no-op today) is populated three ways and the engine is run three times. | **None** |
| **Inflation & salary growth** | Stage 2 of the pipeline, which already exists as a pass-through. Applies growth factors to occurrence amounts before bucketing. Rounding policy defined in §7.4. | **Stage 2 only** |
| **AI financial assistant** | The assistant proposes overlays and events as structured payloads and calls the same public API. It never computes a number. This satisfies RFP §7.4's own requirement that AI must not replace the deterministic engine — and it is a real architectural guarantee, not a promise. | **None** |
| **Actuals / tracking** | The seam already exists and is in use. `balance_as_of` is a user-confirmed reality checkpoint, and the engine already anchors to it. Phase 2 adds an `actual_transactions` table and richer ways to establish that checkpoint — bank sync, marking items paid — plus an `actuals_through` parameter so months at or before it come from actuals. The anchor concept does not change. | **Additive** |
| **Multi-account** | `account_id` on transactions; ledger becomes per-account rows plus a rollup. | **Bucketing only** |
| **Financial health score, freedom planning** | Read-only analytics over an existing ledger. | **None** |

Every Phase 2 item lands as a new *producer* of occurrences or a new *consumer* of the ledger. Nothing reaches into the middle. That is the whole argument, and it is defensible in front of a technical evaluator.

---

## 15. Explicit exclusions & assumptions

To be restated verbatim in the proposal under "Assumptions, Exclusions and Dependencies" (RFP §11).

**Excluded from Phase 1:**
Bank / open-banking integration · actual transaction tracking or reconciliation · multi-account and transfers · multi-currency holdings or FX conversion · offline mode · budgeting or envelope allocation · debt payoff schedules and amortisation tables · investments, assets, net worth · push notifications and reminders · biometric login (architecture-ready, not built) · web or tablet-optimised layouts · third-party analytics beyond a basic product analytics SDK · Hijri calendar support · custom recurrence rules beyond the frozen set · languages beyond Arabic and English.

**Assumptions:**
Client provides and reviews Arabic copy · client provides Apple Developer and Google Play accounts · client supplies branding assets · client nominates one decision-maker for sign-off · client supplies their independently verified test cases during discovery · one primary currency per user, display-only · phone-sized layouts only · the Current Cash Balance is maintained by the user, and the product makes no claim to detect divergence between plan and reality (M1 §3.1).

---

## 16. Open questions for the discovery workshop

### 16.1 Closed at M1

Recorded here so nobody reopens them in a standup. Each is now a signed rule.

| Question | Resolution | Authority |
|---|---|---|
| Accounts — single cash pot? | Yes, single position. Multi-account is Phase 2 | D-03, M1 §10 |
| "Track" — does Phase 1 record actuals? | No. Planning only; the user maintains the balance | D-02, D-04, M1 §3.1 |
| Currency | One currency, display-only, no conversion, with a confirm on change | D-05, M1 R30–R31 |
| Opening balance semantics | Replaced by the Current Cash Balance model: user-confirmed, dated, never system-mutated, anchors the forecast | D-04, M1 R1–R3 |
| Scenario overlay granularity | Field-level, not snapshot | D-11, M1 R19 |
| Archive semantics | Retained, reversible, keeps live inheritance | D-12, M1 R22–R23 |
| Duplicate semantics | Copies overlays, keeps live inheritance, sibling not child | D-13, M1 R24–R26 |
| Base delete with dependents | Cascades, with a warning first | §6.3, M1 R20 |
| Dashboard period | Selected period, forward-only, from the current month | §9.1, M1 R32–R33 |
| Test suite as deliverable | Suite, execution report, CI history and traceability table all handed over | M1 §9.2 |
| Notifications | Out of Phase 1 | M1 §10 |
| Hijri dates | Out, pending final confirmation | M1 §10 |

### 16.2 Still open

Blocking M2 design:

1. **Dark mode** — in or out. Retrofitting a theme across the surface inventory is far more expensive later.
2. **Arabic numerals** — Western digits (0-9) or Eastern Arabic (٠-٩) in Arabic mode.
3. **Chart RTL behaviour** — does the time axis mirror in Arabic? Affects chart implementation cost directly.

Needed during M2:

4. **Outlook indicator rules** — what defines improving / stable / declining. To be agreed with the client, not invented by us (M1 §11.4).
5. **Stale-balance threshold** — how many months before the dashboard prompts. Proposing 30 days (M1 §11.5). Drives the `months_elapsed` comparison in §9.1.
6. **Scenario cap** — any practical limit. Affects the switcher, the compare picker and the duplicate flow.
7. **Onboarding step 3** — guided first income, or land on an empty dashboard.

Needed before development:

8. **Data residency** — must personal financial data stay inside Saudi Arabia? Determines hosting region and running cost.
9. **Transactional email provider** — required for password reset, absent from the RFP.
10. **Analytics platform** — our recommendation requested; affects the privacy policy.
11. **Data export format** — proposing JSON plus full account reset. CSV needed?

Outstanding from the client:

12. **Their independently verified test cases** — to be committed under `fixtures/client/` in the format of M1 §30.

---

## 17. What this unblocks

With this locked, the next two workstreams can run in parallel:

1. **Screen inventory & UX spec** — driven by §4 (what exists), §9 (what the app can ask for) and §9.2 (the inherited/overridden/added editing model, which is the trickiest interaction in the product).
2. **Backend build spec** — schema in §5 is implementation-ready; the engine spec in §7 is detailed enough to be written test-first.

The Flutter developer's contract is the generated OpenAPI spec plus §9.2 and §10. Nothing informal.
