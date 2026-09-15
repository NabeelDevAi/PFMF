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

Each engine test case is a JSON file: an input transaction set, an anchor month, a horizon, and the expected month-by-month ledger. A parametrized test discovers every file in the fixtures directory automatically. This format is chosen specifically so the client's own "independently verified test cases" (referenced in the RFP and both prior docs) can be dropped in as files, with zero code changes, whenever they're obtained — there's a placeholder subdirectory reserved for them now, tracked as an open item in `12-open-questions-and-future-hardening.md` until they arrive.

## 4. Named edge cases (carried forward from the architecture/backend-spec docs)

Monthly recurrence clamping to month-end across a non-leap year · annual recurrence on Feb 29 landing on Feb 28 in non-leap years · weekly recurrence across a five-payday month · an end date before the first possible occurrence yielding zero occurrences · an end date exactly on an occurrence date being inclusive · a one-time transaction before the window · a one-time transaction after the window · a transaction starting before the anchor month contributing only from the anchor forward · an empty scenario producing a flat ledger at the Current Cash Balance · a 120-month horizon with weekly recurrence (performance and correctness together) · an overlay's `unset_end_date` turning a previously-ending transaction open-ended.

## 5. Test database mechanics

The test suite runs Alembic migrations against the dedicated test database once per test session (not the dev database, ever), then uses transaction rollback or truncation between individual tests to keep them isolated from each other without re-running migrations every time. This gives every repository/service/API test real Postgres semantics — real constraints, real cascades, real enum behavior — without needing Docker or testcontainers to get there.
