# Auth & Security

## 1. Password storage

Argon2id via `argon2-cffi`, using its default parameter recommendations rather than hand-tuning them prematurely. Passwords are never logged, never returned in any response, and never stored anywhere but as their hash.

## 2. Tokens

- **Access token:** JWT, 15-minute lifetime, carries the user id (`sub`) and a token id (`jti`). Short-lived enough that no revocation list is needed for access tokens themselves — they simply expire.
- **Refresh token:** an opaque random value, never a JWT. The database stores only its **hash**, never the raw value. Every refresh call rotates it: the old one is marked used, a new one is issued, and both belong to the same "family." If an already-used refresh token is ever presented again, that's a signal of token theft (someone replaying a captured token after the legitimate client already rotated past it) — the entire family is revoked, forcing a fresh login. This requires the refresh-tokens table introduced in `03-database-schema-and-migrations.md`.
- **Logout** revokes the current refresh family. Nothing further is needed since access tokens are already short-lived.

## 3. Ownership enforcement

Every repository method that reads or writes user-owned data takes and filters by `user_id` (see `05-repositories-module.md`). This is treated as the actual security boundary — not the presence of an auth dependency on a router, which is necessary but not sufficient. A missing `@requires_auth`-style decorator on one route should never be able to turn into a data leak, because the query underneath it would still refuse to return another user's row even if it were somehow reached unauthenticated.

A resource that exists but belongs to someone else returns the same `resource.not_found` (404-equivalent) as a resource that doesn't exist at all — see `07-api-layer-and-error-handling.md` for why that's deliberate.

## 4. Rate limiting

Target threshold (kept from the original spec): 5 attempts/minute per IP on login and register. Implemented as an in-memory limiter for this build (see `07-api-layer-and-error-handling.md` §6) rather than a shared/distributed one — sufficient for a single local process, explicitly flagged as needing an upgrade before running as more than one process. (The password-reset rate limit from the original spec, 3/hour per email, no longer applies — see §5.)

## 5. No forgot/reset-password-via-email flow in Phase 1

**Product decision, superseding the original spec.** A transactional email provider was always an unresolved external dependency (not mentioned in the original RFP; flagged as an open question in the screen-flow spec §14 question 5 and M1 §11 item 9: who provides/pays for it). Rather than build the full reset-token flow behind a stubbed sender waiting on that answer, the decision was made to drop the feature from Phase 1 entirely: **a user who forgets their password has no self-service recovery until Phase 2.** They can only change a password they already know, while logged in — `PATCH /v1/me/password`, requiring the current password re-entered plus the new one, and revoking every other session (all refresh-token families, including the one that authenticated the request itself — the client is expected to re-authenticate afterward).

What this removed: `POST /auth/password-reset/request` and `/confirm`, the `password_reset_tokens` table (migration `0014` drops it — migration `0007` that created it is left untouched, migrations are never edited after merge), its repository and model, the stubbed `ConsolePasswordResetSender`, the 3/hour rate limit, and the `auth.reset_token_invalid` error code (replaced by `auth.current_password_incorrect` for the new endpoint). Phase 2 re-adds this schema and flow fresh, informed by whatever email provider is chosen then, rather than resurrecting dormant code that predates that decision.

## 6. Account deletion is a soft delete

**Product decision.** `DELETE /v1/me` doesn't remove the row — it sets `users.deleted_at` and revokes every refresh-token family for that user, then relies on `UserRepository.get_by_id`/`get_by_email` filtering `deleted_at IS NULL` to make the account invisible to every ordinary lookup from that instant on: an already-issued access token fails on its very next request (`get_current_user` re-looks-up the user per request, same mechanism that already made deletion "instant" before this changed), a login attempt fails, and — because email uniqueness is a **partial** index (`WHERE deleted_at IS NULL`, migration `0017`, not the plain constraint the original DDL had) — the same email is immediately available to a brand-new registration, which creates a genuinely new, unrelated row. The result is indistinguishable from a hard delete at the API surface; the difference is that the row and everything it owns (settings, scenarios, transactions, overlays, a profile photo on disk) physically survive. Phase 2 schedules the real purge; `UserRepository.delete()` — the actual cascading hard delete — is already built and tested, just not called by anything in Phase 1. See `12-open-questions-and-future-hardening.md` §9 item 9.

## 7. Transport & storage

TLS termination and encryption-at-rest are deployment-environment concerns (they apply once this runs somewhere other than a local machine) and are out of scope for this plan — tracked in `12-open-questions-and-future-hardening.md` alongside the rest of the deployment story.

## 8. Logging

Structured logs, no financial values and no personally identifying information in them — request ids only, so a specific request can be traced without ever writing a balance, an amount, or an email address to a log file. **Built** (Tier 2 #11, `app/core/logging.py`) — one JSON object per line, a `contextvar` set by `RequestIdMiddleware` correlates every log line during a request without threading the id through every function call by hand. An access-log line per request, auth events (register/login success-or-failure/refresh-reuse-detected/account-deletion) by user id, never by email. Fixed a real gap found while building this: `unhandled_exception_handler` previously returned a generic 500 with zero server-side trace of what broke -- any exception that wasn't a deliberate `APIError` disappeared silently. It now logs with a full traceback (`exc_info=exc`, which works whether or not the handler is running inside an active `except` block, unlike `logger.exception()`).
