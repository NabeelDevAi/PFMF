# The Engine Module

This is the most important document in this folder. Everything else in the backend exists to feed data into this module and carry its output back out. If this module is wrong, no amount of correct CRUD or auth work saves the project.

## 1. The boundary rule

`app/engine/` imports nothing from `app/api`, `app/db`, `app/services`, `app/repositories`, or `app/core`, and nothing from SQLAlchemy, FastAPI, or Pydantic. It receives plain values (numbers, dates, strings, small dataclass-shaped objects) and returns plain values. No database call, no `date.today()`, no randomness, no mutation of its inputs.

That boundary is now held mechanically by `import-linter` (Tier 2 #5, see `12-open-questions-and-future-hardening.md`), not just review discipline. The practical rule while building remains the same: if writing engine code and reaching for anything outside the standard library, stop and ask whether that value should instead be computed by the caller and handed in.

## 2. What lives inside, and the order to build it in

The module is built bottom-up — each piece only ever depends on the ones before it in this list:

1. **Vocabulary** — the closed set of types the whole engine speaks in: a money-as-integer-minor-units type, the direction enum (income/expense), the frozen recurrence enum (the 7 allowed values, no others), an "origin" tag (own/inherited/overridden/added) used later for comparison drivers, and a year-month value that is orderable, hashable, and knows how to add N months and clamp into a target month.
2. **Calendar helpers** — the small set of pure date math this whole product's correctness rests on: how many days a given month has, and how to take an "anchor day" (e.g. the 31st) and clamp it into whatever month you're currently generating an occurrence for. This is deliberately tiny and deliberately gets the most scrutiny.
3. **Value objects** — the shapes that flow through the pipeline: a resolved transaction (what the engine actually consumes — already flattened, no notion of Base/overlay left in it except the `origin` tag for later reporting), an occurrence (one dated, signed instance), a month row, and a ledger (the full output: anchor, horizon, Current Cash Balance, the month rows, and — deliberately — the full occurrence list retained alongside them).
4. **Expansion** — turning one resolved transaction plus a window into every occurrence it produces inside that window. This is the highest-risk logic in the entire product (see §3 below).
5. **Assumptions (the Phase 2 seam)** — in Phase 1 this step does nothing at all; it exists only so the pipeline's shape doesn't change when Phase 2 adds inflation/growth. It is built now, wired into the pipeline now, and left inert.
6. **The forecast pipeline** — expand every transaction, pass the combined occurrence list through the (inert) assumptions step, bucket by month, then accumulate a running balance month by month from the Current Cash Balance. Deterministic ordering of occurrences is preserved even though it doesn't affect the sums, because the month-breakdown feature and any audit output need reproducible ordering, not just reproducible totals.
7. **Compare** — given two ledgers built with the same anchor and horizon, produce the month-by-month deltas (including a percentage that is reported as absent, never zero or infinite, when the baseline month's value is zero) and the "drivers" list: which named transactions (by their stable source id) account for the difference, tagged as added, removed, modified, or unchanged, with unchanged ones dropped from the output. Each driver also carries `active_months` — the count of distinct months it actually occurs in (whichever side has it; B preferred for a modified driver, matching how its name/direction are chosen) — added once a real client screen (the Compare screen's "$X/mo" per driver) needed a way to get a driver's true per-occurrence rate rather than diluting `total_contribution_minor` across the whole horizon, which understates anything added, removed, or otherwise not spanning the full comparison window.

## 3. The single most important rule in this module: clamp, never drift

For month-based recurrence (monthly/quarterly/semiannual/annual), the day-of-month for every occurrence always comes from the **original** start date, clamped into whatever month is currently being generated — never from the previously generated occurrence. A rent transaction starting on Jan 31st produces Jan 31 → Feb 28 → Mar 31 → Apr 30 → May 31. An implementation that walks forward from the last generated date instead of the original start date will drift permanently after the first short month (producing Mar 28 instead of Mar 31), and the error compounds silently for the rest of the horizon. This has a dedicated, named test and is the first thing checked in review of any change to expansion logic.

Leap years are not special-cased — they fall out for free from the same "how many days does this month have" helper that clamping already depends on.

## 4. Boundary and edge behavior the module must get right

- Window boundaries are inclusive at both ends: a transaction dated exactly on the window's first or last day is included.
- A one-time transaction produces exactly one occurrence, and only if its date falls inside the window — otherwise zero, silently, not an error.
- A transaction whose end date falls before its first possible occurrence produces zero occurrences — valid, not an error.
- A transaction that started before the forecast's anchor month still contributes, but only from the anchor month forward — history before the anchor is irrelevant to the ledger.
- An empty scenario (no transactions at all) produces a flat ledger sitting at the Current Cash Balance for every month.
- Weekly/biweekly recurrence is not normalized to a monthly average — a five-payday month is real and must show as five occurrences, not four-and-a-fraction.

## 5. What the engine explicitly does not do

It does not know what a scenario or an overlay is — by the time anything reaches the engine, a service has already flattened a scenario into a plain list of resolved transactions. It does not know what a user is. It does not read the current date — the caller resolves "now" and hands in an explicit anchor month, which is also what makes any forecast exactly reproducible days or months later for QA or the client.

## 6. Definition of done for this module

Every named edge case (see `10-testing-strategy.md`) passes. The reconciliation identity — final balance equals Current Cash Balance plus the signed sum of every occurrence — holds on every fixture and on a set of hand-constructed stress cases. Determinism is verified (same inputs, byte-identical output, run twice). Driver contributions in a comparison sum exactly to the closing-balance delta they explain. No API route exists yet at the point this module is considered done — that's the sequencing signal that it was actually validated in isolation, not against a real database that happened to hide a bug.
