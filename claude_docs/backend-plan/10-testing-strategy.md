# Testing Strategy

## 1. Layers

| Layer | Scope | Infrastructure needed |
|---|---|---|
| Engine unit | Golden fixtures, named edge cases, hand-picked invariant checks | None — pure Python, no database |
| Repository / service integration | Real SQL behavior, cross-user isolation, resolver correctness | The dedicated local test Postgres database (see `02-configuration-and-environment.md`) |
| API integration | Auth, ownership, validation, error codes, full request/response shape | Same local test database, plus a test HTTP client |
| Contract | OpenAPI schema regression | Deferred to the hardening milestone |

## 2. What's built now vs. deferred to the hardening milestone (M6)

This split is the direct consequence of the "lean now, harden later" decision — it is a sequencing choice, not a permanent absence of rigor.

**Built as part of the core milestones:**
- `ruff` for linting/formatting.
- Plain `pytest` across all layers above.
- The full golden-fixture suite for the engine (one JSON file per case, discovered automatically — adding a test case is adding a file, not writing code).
- Every named edge case from the architecture/backend-spec docs, each as its own descriptively-named test.
- A small set of **hand-constructed** invariant checks (`tests/engine/test_invariants.py`, `tests/services/test_scenario_resolver.py`): specific, deliberately varied transaction sets checked against the reconciliation identity, the isolation guarantee, determinism, and driver completeness. Kept as permanent, pinned regression tests even after Hypothesis landed (Tier 2 #6) — the two layers are additive, not a replacement.
- Cross-user isolation tests at the repository layer (user A can never see or affect user B's data).
- Ownership tests at the API layer (another user's resource id returns `resource.not_found`, not a 403 and not the data).

**Done ahead of the M6 hardening milestone (Tier 2, see `12-open-questions-and-future-hardening.md`):**
- ~~`mypy --strict` on `app/engine/`~~ Done, scoped to the engine only (not "standard elsewhere" -- deliberately not expanded).
- ~~`import-linter`~~ Done, both contracts; caught and fixed a real layering violation on its first run.
- ~~Hypothesis property-based tests~~ Done, all four invariants: `tests/engine/test_properties.py` (reconciliation, determinism, driver completeness) and `tests/services/test_scenario_resolver.py` (isolation, against the real database).

**Still deferred to the M6 hardening milestone:**
- GitHub Actions CI running all of the above on every change.
- Coverage gates (100% branch coverage on the engine, ≥85% overall).
- OpenAPI export + regression check (fails if the generated spec changes without being committed).
- Automated migration-drift check (`alembic upgrade head` + autogenerate must show no diff).

## 3. Golden fixtures

Each engine test case is a JSON file: an input transaction set, an anchor month, a horizon, and the expected month-by-month ledger. A parametrized test discovers every file under the fixtures directory automatically, recursively (`tests/engine/fixtures/**/*.json`) — adding a case is adding a file, no code change.

**`tests/engine/fixtures/m1/`** holds every pure-engine case from the signed M1 document's Part 2 (§18–§24, §27.1), named by case number (`22.1.json`, `24.1.json`, ...) so the mapping from file to agreed case is direct, not inferred. Generated once from the doc's own stated occurrence dates and amounts — not by calling the engine and recording its output, which would prove only self-consistency — then run against the real engine as a genuine independent check; all 23 pass byte-for-byte against the doc's figures. A case with two horizon variants (19.3, at 12 and 36 months) gets two files (`19.3_horizon12.json`, `19.3_horizon36.json`). Case 27.2 (horizon choice doesn't change a shared month's figures) isn't a fixed input/output pair, so it's a dedicated test (`tests/engine/test_forecast.py::test_m1_case_27_2_...`) reusing the 27.1 fixture's Base Plan at all four horizons instead.

**`tests/engine/fixtures/client/`** is the still-empty placeholder for the client's own "independently verified test cases" (RFP, referenced in both prior docs) — dropped in as files, zero code change, whenever obtained (tracked as an open item in `12-open-questions-and-future-hardening.md`).

One fixture sits outside `m1/`, at the top level: `end_date_before_first_occurrence_yields_nothing.json` — a genuine architecture §12.2 edge case that isn't one of the 43 numbered M1 cases (M1's own end-date cases, 21.1–21.3, are about a date landing on or before an occurrence, not before the very first one).

## 4. M1 case coverage outside the pure-engine fixtures

Section 25 (the shared Base Plan walked through plan creation, field-level overrides, Base-delete cascades, archive/restore, duplicate — cases 25.1–25.17), section 26 (compare, 26.1–26.3), 27.3 (dashboard periods) and 28.1 (currency) all need the resolver/scenario/overlay machinery, not just the pure engine — they're service/API-level integration tests, not golden fixtures, and are a separate, larger piece of work than the fixture reorganization (tracked in `12-open-questions-and-future-hardening.md` §6 item 9).

The four integrity checks (§29.1–29.4) are already covered: reconciliation and determinism in `tests/engine/test_invariants.py` (hand-picked) and `tests/engine/test_properties.py` (generated); driver completeness in both of those same two files; isolation in `tests/services/test_scenario_resolver.py` (hand-picked and generated). Each test's docstring now cites its check number directly.

## 5. Test database mechanics

The test suite runs Alembic migrations against the dedicated test database once per test session (not the dev database, ever), then uses transaction rollback or truncation between individual tests to keep them isolated from each other without re-running migrations every time. This gives every repository/service/API test real Postgres semantics — real constraints, real cascades, real enum behavior — without needing Docker or testcontainers to get there.
