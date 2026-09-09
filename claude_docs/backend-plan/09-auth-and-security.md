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

Target thresholds (kept from the original spec): 5 attempts/minute per IP on login and register; 3/hour per email on password-reset requests. Implemented as an in-memory limiter for this build (see `07-api-layer-and-error-handling.md` §6) rather than a shared/distributed one — sufficient for a single local process, explicitly flagged as needing an upgrade before running as more than one process.

## 5. Password reset

Requires a transactional email provider, which is an **unresolved external dependency** — not mentioned in the original RFP, and flagged as an open question in the screen-flow spec (§14, question 5: is it in scope, and who pays for the service). Until that's answered, this build implements the full reset-token flow (request → token issued → token validated → password changed) but sends the token through a stubbed sender — for local development, printing/logging it — built behind a small interface so swapping in a real provider later is a one-file change, not a redesign.

## 6. Transport & storage

TLS termination and encryption-at-rest are deployment-environment concerns (they apply once this runs somewhere other than a local machine) and are out of scope for this plan — tracked in `12-open-questions-and-future-hardening.md` alongside the rest of the deployment story.

## 7. Logging

Structured logs, no financial values and no personally identifying information in them — request ids only, so a specific request can be traced without ever writing a balance, an amount, or an email address to a log file. The full structured-logging setup (formatters, correlation of a request id across a whole request lifecycle) is built out during the M2 auth milestone, since that's the first point at which there's meaningful auth-related activity worth logging at all.
