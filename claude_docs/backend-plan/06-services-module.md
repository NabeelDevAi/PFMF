# Services Module

## 1. Purpose

Services are where business rules live and where the persistence world and the engine's pure world meet. A service loads rows via repositories, converts them into the engine's plain value objects (or back into API-ready shapes), calls the engine when a forecast is needed, and enforces every rule that isn't a database constraint.

Routers (the API layer) are not allowed to contain business logic — if a router is deciding something rather than just translating HTTP in and out, that logic belongs in a service instead.

## 2. Services this build needs

| Service | Responsibility | Key rules it enforces |
|---|---|---|
| `AuthService` | Registration, login, token issuance, refresh rotation, logout | Password hashing (Argon2id), refresh token rotation and reuse-detection (revoke the whole family on reuse), rate limiting hooks |
| `SettingsService` | Reading/patching `user_settings` | Opening balance and its effective date are user-entered, not derived |
| `CategoryService` | Listing system + user categories, creating user categories | System categories are read-only to the user; only user-created ones can be added/edited |
| `ScenarioService` | Scenario CRUD, duplicate, archive/unarchive | **Base can never be deleted or archived, and a second Base can never be created** — enforced here, backed by the DB's partial unique index; duplicating a scenario copies its own transactions and overlays, and does not create a parent link (flat, one level deep) |
| `TransactionService` | Transaction CRUD | Direction is immutable after creation (changing income↔expense is delete-and-recreate, not edit); a transaction's recurrence/date fields obey the frozen recurrence set and the one-time-has-no-end-date rule; per-scenario transaction count cap |
| `OverlayService` | Creating/patching/deleting overlays | An overlay may only target a Base transaction; only one overlay may exist per (scenario, target) pair; deleting an overlay reverts that transaction to plain inheritance; `unset_end_date` is the only way to turn a previously-ending Base transaction open-ended in an overlay |
| `ScenarioResolver` | Turning a scenario into a flat list of resolved transactions the engine can consume | Implements the resolution algorithm from architecture §6 exactly: Base returns its own rows as-is; a derived scenario walks Base's transactions, applies an overlay if one targets that transaction (exclude → drop it, override → patch it), then appends the scenario's own local transactions. This is the single service with the heaviest test-coverage expectation in the whole backend — it is the bridge between messy, mutable persistence and the engine's pure world, and every bug that could ever leak into a client's real financial data would leak in here. |
| `ForecastService` | Resolving `anchor_month` (from the clock, if not given explicitly) and horizon, calling the resolver, calling the engine, shaping the ledger into an API response | The engine itself never reads a clock — this service is where "now" is decided, exactly once, at the edge |
| `CompareService` | Running the forecast twice (for scenario A and B) and calling the engine's compare function | Rejects comparing a scenario with itself; both ledgers must share anchor and horizon before comparing |

## 3. What a service is not allowed to do

Issue SQL directly (that's the repository's job) or perform financial arithmetic itself (that's the engine's job, exclusively — a service prepares inputs for the engine and relays its outputs, and never re-derives a balance, a delta, or a percentage on its own).

## 4. Testing plan

Most services get unit tests exercising their business rules directly (Base immutability, direction immutability, overlay target validation, duplicate-overlay rejection, and so on) without necessarily hitting a real database for every case. `ScenarioResolver` and anything touching multiple repositories in a way that could hide a real SQL bug gets integration tests against the local test database instead, because the risk there is specifically about real persistence behavior, not just logic.
