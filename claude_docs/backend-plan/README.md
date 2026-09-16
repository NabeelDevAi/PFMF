# Horizon Backend — Development Plan

**Status:** Draft v1.0 — planning artifact, no code yet
**Depends on:** `phase1-system-architecture.md`, `phase1-backend-build-spec.md`, `phase1-screen-flow-spec.md`
**Purpose:** Translate the locked architecture and the original backend build spec into a build plan for the *actual* environment we're building in — a single developer, local Postgres, no Docker, no cloud infra yet.

This folder is the working plan. It contains no code — only module boundaries, responsibilities, sequencing, and the API surface, organized the way the codebase itself will be organized, so each doc here maps to a future part of the repo.

---

## 1. What's simplified from the original backend build spec, and why

The backend build spec (`phase1-backend-build-spec.md`) was written assuming a team, Docker everywhere, testcontainers, and full CI/CD from sprint 0. We are one developer building against a **local PostgreSQL 18 instance already running on this machine**, with no Docker. Four decisions were made explicitly to adapt the spec to that reality, rather than silently drifting from it:

| Area | Original spec | This build | Why |
|---|---|---|---|
| DB access | Async SQLAlchemy 2.x (asyncpg) | **Sync SQLAlchemy 2.x** | No concurrency need at this scale; sync is a simpler mental model with fewer failure modes to debug alone. |
| Dependency management | `uv` + lockfile | **pip + venv** | A venv already exists on this machine; no new tool to adopt. |
| Engineering rigor (mypy strict, import-linter, Hypothesis, CI) | All in place from Sprint 0 | **Deferred to a dedicated hardening milestone (M6)** | Get the engine and API working and correctly tested first; add the enforcement machinery once the shape of the code is proven, not before. |
| Integration test database | testcontainers (spins up disposable Postgres in Docker) | **A dedicated local Postgres test database on the existing instance** | No Docker available; the existing local Postgres 18 server plays the same role directly. |

Also noted, not requiring a decision: the spec assumes Python 3.12; this machine has **Python 3.14.4** already set up in the project's `venv/`. We build against 3.14 and only reconsider if a required dependency doesn't yet support it.

**What is unchanged — these are non-negotiable regardless of simplification:**
- The engine (`app/engine/`) is pure: no I/O, no framework imports, no clock, no floats for money.
- The engine is built and fully tested *before* any API route exists.
- Layering direction: `api → services → repositories → db`, engine depends on nothing.
- Every repository query is scoped by `user_id`.
- Money is integer minor units always; dates are `DATE` only; the frozen 7-item recurrence set; clamp-never-drift for month-based recurrence.
- Overlay editing semantics (§9.2 / §4.4): editing an inherited transaction in a non-Base scenario creates/patches an overlay, never touches the Base row.
- The server never returns display-formatted text — machine error codes only, client-owned language.
- One forecast endpoint feeds the dashboard, all chart views, the table, and the month breakdown. No `/dashboard`, no `/charts`.

---

## 2. How this folder is organized

| Doc | Covers |
|---|---|
| `01-repo-layout-and-conventions.md` | Directory structure, naming, coding conventions |
| `02-configuration-and-environment.md` | Settings, local Postgres setup, secrets handling |
| `03-database-schema-and-migrations.md` | Schema (incl. the refresh-token addition), Alembic plan |
| `04-engine-module.md` | The pure forecasting engine — the most important document here |
| `05-repositories-module.md` | The data access layer |
| `06-services-module.md` | Orchestration layer — where persistence meets the engine |
| `07-api-layer-and-error-handling.md` | Routing, auth wiring, error envelope, conventions |
| `08-api-endpoints-plan.md` | Every endpoint, resource by resource — the API-wise plan |
| `09-auth-and-security.md` | Auth flows, tokens, rate limiting, ownership enforcement |
| `10-testing-strategy.md` | What's tested, how, and with what infrastructure, now vs. later |
| `11-build-order-and-milestones.md` | The sequencing plan — read this to know what to build next |
| `12-open-questions-and-future-hardening.md` | Everything deliberately deferred or still unresolved |

**If you only read one file to know what to do next, read `11-build-order-and-milestones.md`.**

---

## 3. The one idea to hold onto

Every other document in this folder exists in service of one fact: **the forecast is a pure function, and it is the only part of this system the client's acceptance criteria actually test.** Everything else — auth, CRUD, HTTP — is necessary plumbing around it, but the plumbing failing is a bug; the engine failing is a failed project. The build order reflects that on purpose.
