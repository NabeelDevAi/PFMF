# The Engine

Pure. No imports from `app.api`, `app.db`, `app.services`, `app.repositories`, `app.core`, and none of SQLAlchemy/FastAPI/Pydantic. Plain values in, plain values out. See `claude_docs/backend-plan/04-engine-module.md` for the full design rationale.

**Module order (each depends only on the ones before it):**

`types.py` → `calendar.py` → `models.py` → `expand.py` → `assumptions.py` (Phase 2 seam, inert) → `forecast.py` (the pipeline) → `compare.py`

**The one rule that matters most:** in `expand.py`'s month-based expansion, the anchor day always comes from the transaction's original `start_date` -- never from a previously generated occurrence. That's the entire clamp-vs-drift bug, in one sentence.

**Not built here yet:** `mypy --strict` / `import-linter` enforcement of the purity rule above is deferred to the hardening milestone (M6) -- for now it's held by review discipline. See `claude_docs/backend-plan/12-open-questions-and-future-hardening.md`.
