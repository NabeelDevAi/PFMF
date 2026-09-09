# Build Order & Milestones

**Read this document to know what to build next.** The sequencing philosophy from the original backend build spec is kept exactly: the engine ships before anything can call it, because it's the only part of this system that can fail the client's acceptance criteria. Everything here is a milestone (done when a specific, checkable condition is true), not a calendar sprint — this is a solo build, and milestones don't need a fixed duration attached to them.

## M0 — Foundation

**Delivers:** repo skeleton matching `01-repo-layout-and-conventions.md`, configuration loading (`02-configuration-and-environment.md`), the local dev database and the separate local test database both created and reachable, a basic health-check route.

**Done when:** the app starts locally, connects to the dev database, and the test database is confirmed reachable and migratable. No CI yet — that's deferred to M6.

## M1 — Engine

**Delivers:** the full engine module exactly as described in `04-engine-module.md` — types, calendar helpers, value objects, expansion, the inert assumptions seam, the forecast pipeline, compare — plus its complete test suite (golden fixtures, every named edge case, the hand-picked invariant checks).

**Done when:** every named edge case passes under its own descriptive test name, the reconciliation identity holds on every fixture and stress case, determinism is confirmed, and driver completeness holds on comparison cases. **No API route exists yet at this point** — that absence is the actual proof that the engine was validated on its own terms, not against a database that happened to paper over a bug.

## M2 — Auth & identity

**Delivers:** register, login, refresh (with rotation and reuse-detection), logout, `GET/PATCH /me` and settings, category listing (with the seed migration for system categories in place), the password-reset token flow behind a stubbed sender, in-memory rate limiting on the auth routes.

**Done when:** the full auth API is exercised by integration tests against the local test database, rate limits are demonstrably enforced, and a reused refresh token is proven to revoke its whole family.

## M3 — Scenarios & transactions

**Delivers:** scenario CRUD (create, rename, duplicate, archive/unarchive, delete), Base-plan protection, transaction CRUD scoped to the scenario a caller owns directly.

**Done when:** Base cannot be deleted or archived through any code path, a second Base cannot be created, ownership is enforced on every route (another user's id returns `resource.not_found`), and direction is proven immutable after creation.

## M4 — Overlays & resolution

**Delivers:** overlay create/patch/delete, the `ScenarioResolver` service, the resolved-transactions-list endpoint (with `origin` on every row).

**Done when:** the isolation guarantee — arbitrary overlays on one scenario never affecting another scenario's resolved list or ledger — is proven against the real database, not just in engine-level unit tests. This is the milestone where the architecture's single biggest risk (§9.2 / screen-flow §4.4) either holds or doesn't, and it gets the most scrutiny of any milestone after the engine itself.

## M5 — Forecast & Compare API

**Delivers:** the forecast endpoint and the compare endpoint, wired through `ForecastService`/`CompareService` to the engine built in M1.

**Done when:** a request through the actual HTTP API produces a ledger matching the engine-level golden fixtures exactly — proving the whole chain (persistence → resolution → engine → response shaping) preserves what M1 already proved in isolation. If the client's own verified test cases have been obtained by this point, they're run end-to-end here too.

## M6 — Hardening

**Delivers:** everything deliberately deferred throughout the plan — `mypy --strict` on the engine, `import-linter` boundary enforcement, Hypothesis property-based fuzzing (upgrading M1's hand-picked invariant checks), GitHub Actions CI, coverage gates, OpenAPI export + regression checks, an automated migration-drift check, a revisit of the in-memory rate limiter, and a first real look at deployment packaging (Docker or otherwise) if and when that becomes the next actual need.

**Done when:** the enforcement machinery described above is running and green, not merely planned.

## Definition of done, per endpoint (applies from M2 onward)

Implemented · unit and/or integration tested per `10-testing-strategy.md` · ownership enforced · errors use registry codes from `07-api-layer-and-error-handling.md` · migration (if any) reviewed by hand. ("OpenAPI accurate" and "CI green" are added to this list starting at M6, once those tools exist.)

## The one instinct to resist

Every instinct on a project like this says to start with login screens because there's something to demo. Resist it here too, even solo — the engine has zero infrastructure dependencies and carries all of the acceptance risk; finishing it first means it can be checked against the client's own test cases (once obtained) while nothing else has even been started.
