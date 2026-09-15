# API Layer & Error Handling

## 1. Purpose and boundaries

The API layer does exactly three things: authenticate the caller, validate the request shape, and call a service — then shape whatever the service returns into an HTTP response. It contains no business logic and performs no arithmetic. If a router needs an `if` statement to decide something about the user's data rather than about the HTTP request itself, that decision belongs in a service.

## 2. Shared dependencies

- **Current user resolution** — every authenticated route depends on extracting and validating the access token and resolving it to a user id, which is then the `user_id` threaded into every repository call underneath it. There is no route that reaches a repository without this having happened first (except the handful of genuinely public routes: register, login, refresh, password-reset request).
- **DB session** — one request-scoped session, handed to services, closed at the end of the request.
- **Anchor/clock resolution** — the *only* place "today" is read is here, in the forecast/compare routes, before calling `ForecastService`. The engine never sees a clock; this layer is where that promise is actually kept.

## 3. Error envelope

Every non-2xx response has the same shape: a machine-readable code, optional structured parameters describing what specifically failed, and a request id. The server never sends a human-facing sentence — that's the client's job, keyed off the code (this is what makes Arabic/English a client-only concern, per the architecture doc's localization rules).

Every response, success or failure, carries a request id header, so a client-reported bug can be traced back to a specific request without needing to log any financial values.

## 4. Error code registry

This table is a contract with the mobile client as much as it's an internal reference — every code needs an Arabic and English string on the Flutter side, and adding a new code without updating that side ships an untranslated error message to a real user.

| Code | HTTP | Meaning |
|---|---|---|
| `auth.invalid_credentials` | 401 | Email or password is wrong |
| `auth.email_taken` | 409 | Registration attempted with an email already in use |
| `auth.token_expired` | 401 | Access token expired — client should refresh |
| `auth.token_invalid` | 401 | Malformed or revoked token |
| `auth.weak_password` | 422 | Password below policy |
| `auth.reset_token_invalid` | 422 | Password-reset token invalid, expired, or already used |
| `balance.as_of_in_future` | 422 | `PUT /me/balance`'s as-of date is later than today |
| `balance.as_of_too_old` | 422 | `PUT /me/balance`'s as-of date is beyond the 5-year backstop |
| `validation.required` | 422 | A required field is missing |
| `validation.invalid` | 422 | Generic field validation failure |
| `transaction.amount_not_positive` | 422 | Amount is zero or negative |
| `transaction.end_before_start` | 422 | End date precedes start date |
| `transaction.one_time_has_end_date` | 422 | A one-time transaction was given an end date |
| `transaction.direction_immutable` | 422 | Attempt to flip income ↔ expense on an existing transaction |
| `scenario.base_immutable` | 409 | Attempt to delete or archive the Base plan |
| `scenario.name_taken` | 409 | Duplicate scenario name for this user |
| `scenario.archived` | 409 | An archived scenario used as a comparison operand or a duplicate source |
| `scenario.not_archived` | 409 | Unarchive attempted on a scenario that isn't archived |
| `overlay.target_not_in_base` | 422 | An overlay was pointed at a transaction that isn't in Base |
| `overlay.already_exists` | 409 | A second overlay was attempted against the same target |
| `overlay.scenario_is_base` | 422 | An overlay was attempted on the Base scenario itself |
| `category.in_use` | 409 | Deleting a user category still referenced by a transaction or an overlay |
| `compare.same_scenario` | 422 | Plan A and Plan B are the same scenario |
| `forecast.invalid_horizon` | 422 | Horizon is outside `[1, max_horizon_months]` |
| `resource.not_found` | 404 | Also returned when the resource exists but belongs to another user |
| `rate_limited` | 429 | Too many attempts on a rate-limited route |
| `internal` | 500 | Unhandled server error |

**No cap on the number of scenarios or transactions an account can hold** — `scenario.limit_reached` and `transaction.limit_reached` existed briefly this build (a 50-plan / 500-per-scenario product decision, made when neither locked doc addressed the question) and were removed by explicit later decision. If a cap is wanted again, it returns as a new code through the same reviewed-change process as any other addition here, not a silent revert.

**`resource.not_found` for another user's resource is deliberate, not a bug to fix later.** Returning 403 instead would confirm to a caller that the resource exists at all, which is itself information leakage in a financial product.

## 5. Response conventions

- Every money field is a plain integer in minor units, and its field name is suffixed `_minor`.
- Months are `"YYYY-MM"` strings; dates are `"YYYY-MM-DD"`. No timestamps appear anywhere in a financial payload.
- Currency is always a separate ISO code field — never a symbol, never baked into a formatted string.
- Every list response is wrapped in an `items` field rather than returned as a bare array, so pagination can be introduced later without breaking existing clients.

## 6. Rate limiting (adapted for this build)

The original spec's rate limits (5/min on login and register per IP, 3/hour on password reset per email) are kept as the target numbers, but implemented as a simple **in-memory** limiter for now rather than a Redis-backed one — there's a single process on a single machine, so in-memory state is sufficient. This is explicitly listed in `12-open-questions-and-future-hardening.md` as something to revisit before this ever runs as more than one process (an in-memory limiter's counters don't survive a restart or coordinate across processes, which matters once there's more than one).
