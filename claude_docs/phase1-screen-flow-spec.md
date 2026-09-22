# Phase 1 — Screen Flow & UX Specification

**Status:** v1.1 — aligned to signed M1
**Owner:** Nabeel Sohail (Technical Lead / Architect)
**Depends on:** `phase1-system-architecture.md` v1.1 (domain model §4, API §9, overlay editing §9.2, localization §10)
**Authority:** `Milestone 1 — Discovery & Specification v1.1` — Part 1 §5 for screen content, Part 2 for behaviour
**Audience:** UI/UX designer, Flutter developer, QA

**Changes in v1.1:** Dashboard now shows two distinct balance figures and a period selector (§5.1) · new surface B3 for updating the Current Cash Balance (§5.3) · surface count corrected to 37 (the v1.0 total of 34 was an arithmetic error — the inventory rows have always summed to 36, plus B3 makes 37) · field-level change display on transactions (§6.2) · dependents warning when deleting a Base item (§6.4) · archive, restore and duplicate copy (§8) · two-balance naming discipline added to the copy rules (§10).

---

## 1. How to read this document

This is a **structural** spec, not a visual one. It defines what screens exist, what each one contains, what states it can be in, and how the user moves between them. It deliberately does not specify colours, fonts, spacing or illustration style — those are the designer's to own, guided by §11.

| Role | Read this for |
|---|---|
| **Designer** | §2 navigation, §3 inventory, §4 flows, §5–9 screen contents & states, §10 copy rules, §11 direction, §12 deliverables |
| **Flutter developer** | §2 navigation, §5–9 (each screen names its API calls), §4.4 the critical flow, §13 estimation |
| **QA** | §5–9 states and edge cases, §4 flows for UAT scripts |

The rule for every screen: **the app renders, the server calculates.** No screen computes a balance, a net, a total or a projection. Every number displayed comes from a server payload. Where a screen shows a derived figure (annual totals from monthly rows), it is a plain sum of integers the server already sent.

---

## 2. Navigation architecture

### 2.1 The central IA decision: scenario is a global context

The user is always viewing the app **through one active plan**. Switching the active plan changes what the Dashboard, Transactions and Forecast tabs show. Base Plan is the default and the app opens there every session.

**Why this and not the alternative.** The alternative is to make Base the permanent subject of the app and treat scenarios as documents you open. That reads cleaner but breaks the moment the user wants to answer "what does my year look like if I buy the house" — they would have to leave their normal view and enter a parallel, lesser version of the app. Making the plan a context means the full app works for every plan, and comparison becomes a natural thing to reach for rather than a separate feature.

**The risk this creates, and how design must handle it.** A user who forgets they are in "Buy House" and edits their salary will believe they changed their real plan. This is the single biggest usability risk in the product, and it maps directly onto the architectural risk in §9.2 of the architecture doc. Three mitigations, all mandatory:

1. A **persistent plan indicator** in the header of every tab. Not a small label — a tappable chip carrying the plan name.
2. **Non-Base plans are visually marked.** An accent treatment (colour bar, tinted header, or equivalent — designer's call) that is present on every screen while a non-Base plan is active. Base has no marking, so "unmarked = my real plan" becomes learnable.
3. **Write actions name the plan.** Save confirmations and toasts say which plan was changed: "Added to Buy House," not "Added."

### 2.2 Tab structure

Four tabs. Settings is reached from the Dashboard header, not a tab — it is low-frequency, and four tabs keep Arabic labels legible at phone widths.

```
┌─────────────────────────────────────────────────┐
│  [Plan: Base Plan ▾]                    [⚙]     │  ← persistent header
├─────────────────────────────────────────────────┤
│                                                 │
│                  screen body                    │
│                                                 │
├─────────────────────────────────────────────────┤
│   Home      Transactions    Forecast    Plans   │
└─────────────────────────────────────────────────┘
```

| Tab | Job |
|---|---|
| **Home** | Where do I stand today, and where am I heading |
| **Transactions** | The assumptions that drive everything |
| **Forecast** | The projection, in chart and table |
| **Plans** | Manage scenarios, and compare them |

Tab order mirrors under RTL (Home sits on the right in Arabic). The plan chip and settings icon swap sides. Tab **order** does not reverse in the data sense — Home remains the first tab, it simply renders from the right.

### 2.3 Map

```
Splash ─┬─ (no session) ─→ Welcome ─┬─→ Login ─────────┐
        │                            └─→ Register ──→ Onboarding (3 steps)
        │                                                   │
        └─ (session) ────────────────────────────────────→ MAIN
                                                            │
   ┌────────────────────────┬───────────────┬───────────────┴──────────┐
   │                        │               │                          │
  HOME                 TRANSACTIONS      FORECAST                    PLANS
   │                        │               │                          │
   ├─ Plan switcher ⌄       ├─ Add/Edit     ├─ Horizon picker ⌄        ├─ Create plan
   ├─ Settings ⚙            │   ├─ Category │                          ├─ Plan detail
   └─ (deep links into      │   └─ Schedule └─ Month breakdown         └─ Compare
       Forecast / Txns)     └─ Remove confirm                              ├─ setup
                                                                           └─ results
```

---

## 3. Screen inventory

**37 surfaces total: 26 full screens, 11 modals/sheets/dialogs.** This is the number to design against and to estimate against.

One surface was added in v1.1: **B3 — Update Current Cash Balance.** The dashboard period selector is an inline segmented control, not a separate surface.

**Correction to v1.0:** that version stated 34 surfaces while its own inventory rows summed to 36. The table was right and the total was wrong. With B3 the correct figure is **37**, and the estimation table in §13 now reconciles to it. Design and estimation should both use 37.

| ID | Screen | Type | Complexity |
|---|---|---|---|
| **A — Auth & Onboarding** ||||
| A1 | Splash / session bootstrap | Screen | S |
| A2 | Welcome + language select | Screen | S |
| A3 | Register | Screen | M |
| A4 | Login | Screen | S |
| A5 | Forgot password — request | Screen | S |
| A6 | Reset password — set new | Screen | S |
| A7 | Onboarding 1 — currency | Screen | S |
| A8 | Onboarding 2 — current cash balance | Screen | M |
| A9 | Onboarding 3 — first income (skippable) | Screen | M |
| **B — Home** ||||
| B1 | Dashboard | Screen | **XL** |
| B2 | Plan switcher | Sheet | S |
| B3 | Update current cash balance | Sheet | M |
| **C — Transactions** ||||
| C1 | Transactions list | Screen | **L** |
| C2 | Add / edit transaction | Screen | **L** |
| C3 | Category picker | Sheet | M |
| C4 | Schedule picker (frequency + dates) | Sheet | **L** |
| C5 | Remove / delete confirm | Dialog | M |
| C6 | Transaction filter | Sheet | S |
| **D — Forecast** ||||
| D1 | Forecast (chart + monthly table) | Screen | **XL** |
| D2 | Month breakdown | Sheet | M |
| D3 | Horizon picker | Sheet | S |
| **E — Plans** ||||
| E1 | Plans list | Screen | M |
| E2 | Create plan | Screen | M |
| E3 | Plan detail | Screen | M |
| E4 | Compare — setup | Screen | M |
| E5 | Compare — results | Screen | **XL** |
| E6 | Plan actions (rename/duplicate/archive/delete) | Sheet | S |
| **F — Settings** ||||
| F1 | Settings home | Screen | S |
| F2 | Profile | Screen | S |
| F3 | Currency | Screen | S |
| F4 | Language | Screen | S |
| F5 | Current cash balance | Screen | M |
| F6 | Change password | Screen | S |
| F7 | Export data | Screen | S |
| F8 | Reset data | Dialog | M |
| F9 | Delete account | Dialog | M |
| F10 | About & legal | Screen | S |

The four **XL/L-heavy** screens — Dashboard, Transactions list, Forecast, Compare results — carry most of the product's value and most of its risk. They should be designed first and prototyped first. The Dashboard moved from L to XL in v1.1: it now carries two balance figures, a period selector and a stale-balance prompt, and getting the two balances visually distinct is the most consequential single decision on the screen.

---

## 4. Core flows

### 4.1 First launch

```
Splash → Welcome (pick العربية / English) → Register
   → Onboarding 1: currency (default SAR)
   → Onboarding 2: current cash balance ("how much do you have right now?")
   → Onboarding 3: add your income  [Skip]
   → Dashboard (Base Plan)
```

Onboarding 3 exists so the first Dashboard is not empty. A forecasting app whose first screen is a flat zero line teaches the user nothing. If skipped, the Dashboard shows a purposeful empty state (§5.1) rather than zeros.

Language is chosen **before** account creation, so registration itself is already localized.

**Onboarding 2 sets the anchor for everything.** The figure the user enters here is their Current Cash Balance, and the date becomes the point the whole projection is built from. The app records today's date automatically — the user is not asked for it, because at onboarding it is always now. The screen should ask plainly for what they have right now, and should avoid the word "opening", which invites them to think of a statement period rather than their position today.

### 4.2 Adding a recurring expense

```
Transactions → [+] → C2 form
   name → amount → income/expense → category (C3)
   → schedule (C4): frequency, start date, optional end date
   → Save → back to list, new row highlighted
   → Forecast and Dashboard reflect it on next load
```

The form is one screen with two sheet-based sub-pickers, not a wizard. Users add many transactions in a row during setup; a multi-step wizard makes that painful.

### 4.3 Creating and shaping a plan

```
Plans → [Create plan] → name it ("Buy House")
   → app switches active plan to Buy House
   → Transactions now shows Base's transactions, each marked "From Base"
   → user adds "Mortgage" (scenario-only)
   → user edits "Rent" → becomes "Modified"
   → user removes "Savings transfer" → becomes "Removed from this plan"
   → Forecast reflects all of it; Base is untouched
```

### 4.4 ⚠ Editing an inherited transaction — the critical flow

This is where a misunderstanding silently corrupts the user's real plan. It must be unmistakable in the design.

```
Active plan = "Buy House" (non-Base)
User opens "Rent" — badge reads "From Base"

  ┌─ user changes amount and saves ────────────────────┐
  │  App calls POST /scenarios/{id}/overlays (override)│
  │  NOT PATCH /transactions/{id}                      │
  │  Badge becomes "Modified"                          │
  │  Toast: "Rent updated in Buy House"                │
  │  A "Revert to Base" action appears                 │
  └────────────────────────────────────────────────────┘

  ┌─ user removes it ──────────────────────────────────┐
  │  Button reads "Remove from this plan" — NOT "Delete"│
  │  App calls POST /overlays (exclude)                │
  │  Confirm copy: "Rent stays in your Base Plan."     │
  └────────────────────────────────────────────────────┘

  ┌─ same actions while active plan = Base ────────────┐
  │  Button reads "Delete"                             │
  │  Confirm warns it affects plans that inherit it    │
  └────────────────────────────────────────────────────┘
```

**Three badge states, on every transaction row and detail screen in a non-Base plan:**

| Badge | Meaning | Available actions |
|---|---|---|
| **From Base** | Inherited, unmodified | Edit → creates override · Remove from this plan |
| **Modified** | Overridden here | Edit · **Revert to Base** · Remove from this plan |
| **Only in this plan** | Scenario-local | Edit · Delete |

In the Base Plan, no badges appear at all — every row is simply a transaction. Badges are a signal that you are somewhere other than home.

Excluded transactions are **not** hidden from the list. They appear greyed with a "Removed from this plan" state and an **Undo** action, because a silently vanished row is indistinguishable from a bug, and the user needs a way back.

**"Modified" means specific fields, not the whole item.** A plan holds only the fields the user actually changed; everything else still follows Base and updates when Base updates. The detail screen must show which fields differ, per field:

```
Rent                                    [Modified]
  Amount       SAR 5,000     From Base
  Schedule     Monthly       From Base
  Ends         31 May 2026   Changed in this plan
                                  [Revert to Base]
```

This is not cosmetic. It is the only way a user can understand why their plan's rent amount changed when they never touched it — the answer being that they never overrode the amount, so it follows Base. Without this display, correct behaviour (M1 case 25.11) looks like a bug. "Revert to Base" clears every override on the item at once; per-field revert is not in Phase 1.

### 4.5 Comparing

```
Plans → [Compare] → E4: pick Plan A (default: Base), Plan B, horizon
   → E5 results: chart with two lines, delta summary, "What's driving this",
     monthly table with A / B / difference
```

### 4.6 Updating the current cash balance

```
Dashboard → stale-balance prompt  (or Settings → F5)
   → B3 sheet: "How much do you have right now?"
   → amount + as-of date (defaults to today)
   → preview: "Your projection will be rebuilt from June 2026."
   → Confirm
   → Dashboard, Forecast and every plan rebuild from the new anchor
```

This is the closest thing Phase 1 has to recording reality, so it should feel deliberate rather than incidental. Three rules for the design:

1. **Nothing else in the app writes this figure.** No transaction, no plan change, no passage of time. If a user could see the balance move on its own, the entire distinction between the two balance figures would collapse.
2. **The as-of date is shown and editable**, defaulting to today. A user reconciling from a statement may be entering last Friday's figure.
3. **The consequence is previewed before confirming.** Changing it re-anchors every projection in every plan, which is a bigger effect than any other single edit in the product.

---

## 5. Home

### 5.1 B1 — Dashboard

Maps to RFP §4.2 and M1 §5.2. The single most-viewed screen, and the one carrying the most agreed behaviour.

**Header:** plan chip (tappable → B2) · settings icon.

#### The two balances — the defining decision on this screen

The dashboard shows two balance figures, and **the user must never confuse them.** This is a signed distinction (M1 R1–R3), not a presentational preference.

**Current Cash Balance** — what the user entered and confirmed, shown with the date they confirmed it. Nothing in the app changes it. It does not respond to the period selector.

**Projected Balance** — what the engine calculated from that figure plus scheduled items. It responds to the period selector.

The first is something the user knows. The second is something the app worked out. If the design lets them read as two variants of one number, the product is making a claim it cannot support — Phase 1 has no way to know whether a scheduled salary actually arrived.

What this demands of the design:

- **Different visual treatment, not just different labels.** Size, weight, container or position — something that survives a glance. Two similarly-styled large numbers stacked together is the failure mode.
- **The Current Cash Balance is always shown with its date.** "SAR 45,000 · as of 1 Jan 2026." Never a bare figure — five months later a bare figure is simply wrong, with nothing on screen to say so.
- **The Projected Balance always names its horizon.** "SAR 163,200 projected by Jun 2026." Never an unlabelled number.
- Designer's call which of the two leads. There is a real argument either way: the confirmed figure is what the user trusts, the projected figure is what the product is for.

#### Content

1. **Current Cash Balance**, with its as-of date and a tap target → B3 to update it.
2. **Period selector** — This month · Next 3 months · Next 6 months · Next 12 months. An inline segmented control. Forward-only (M1 R33).
3. **Income · Expenses · Net cash flow** for the selected period. Net must be visually distinct from either balance — these are the figures users most often conflate.
4. **Projected Balance** at the end of the selected period.
5. **Outlook indicator** — improving / stable / declining across the selected period. Rules to be agreed with the client (M1 §11.4); it must be defensible, not vibes.
6. **Stale-balance prompt**, when the as-of date is older than the agreed threshold: "Your balance is from 5 months ago. Update it to keep your projection accurate." → B3. Persistent but dismissible; never a blocking modal, and dismissing it changes no figure.
7. **Mini balance chart** — 12 months, tappable → Forecast tab.
8. **Quick add** button.

**API:** one call — `GET /v1/scenarios/{active}/forecast?horizon=<months_elapsed + 12>`. Every figure above is read from that payload. `current_balance_minor` and `balance_as_of` give the first figure, the monthly rows give the rest, and `months_elapsed` drives both the period window and the stale prompt. The period selector does **not** trigger a new request — all four windows are slices of the same payload.

**States:**
- *Loading* — skeletons in the shape of the real content, not a centred spinner.
- *Empty* (no transactions) — not zeros. The Current Cash Balance still shows, because the user entered it; the projection area carries the invitation: "Add your income to see your projection." One primary action.
- *Error* — inline retry, previous data retained if present.
- *Stale balance* — the prompt above, over otherwise normal content.

**RTL:** amount + currency ordering follows locale; the mini chart's time axis direction is a decision flagged in §11.3.

### 5.2 B2 — Plan switcher (sheet)

List of plans, active one marked, Base always first and labelled. "Create plan" at the bottom. Archived plans are not listed here. Selecting switches context app-wide and returns to the current tab.

### 5.3 B3 — Update current cash balance (sheet)

New in v1.1. Reached from the dashboard balance, from the stale-balance prompt, and from Settings F5.

**Contents:** amount (numeric keypad, currency affix) · as-of date, defaulting to today · a one-line preview of the consequence: *"Your projection will be rebuilt from June 2026."* · Confirm and Cancel.

**Copy:** ask for what they have, not for a system concept. "How much do you have right now?" Not "Set opening balance."

**API:** `PUT /v1/me/balance`. This is the only call in the app that writes this figure (architecture §9.2).

On confirm, every projection in every plan re-anchors. The sheet should acknowledge that plainly rather than closing silently, because the user has just changed every number in the product.

**Not** an inline editable field on the dashboard. A figure this consequential should not be one mis-tap from being overwritten.

---

## 6. Transactions

### 6.1 C1 — Transactions list

Maps to RFP §4.3.

**Content:** grouped by income / expense (or a segmented control between them — designer's call, but the two must never be summed together visually). Each row: name, amount, category, schedule summary ("Monthly, from 1 Jan"), and — in non-Base plans — its badge.

**Includes:** filter (C6: type, category, active/ended), search by name, `[+]` add.

Rows for ended transactions are shown with their end date, not hidden. A transaction that stopped last year still explains last year's forecast.

**API:** `GET /v1/scenarios/{id}/transactions` — the resolved view, each row carrying `origin`, which is what the badge renders from.

**States:** loading skeleton · empty ("Nothing here yet. Add your salary, rent, or a subscription.") · filtered-empty (distinct copy + clear filters action) · error.

### 6.2 C2 — Add / edit transaction

One screen, three modes: create · edit-own · edit-inherited (§4.4).

**Fields:** name · amount (numeric keypad, currency affix by locale, minor units, no negatives) · income or expense (segmented, required, **not editable after creation** — architecture doc D-note; changing direction means delete and re-add) · category (C3) · schedule (C4) · notes (optional).

**Validation, inline, on blur:** name required · amount > 0 · end date not before start date · one-time transactions have no end date. All messages come from server error codes or client rules, localized — never raw server English.

**Bottom actions:** Save · (edit mode) Remove from this plan / Delete · (modified mode) Revert to Base.

**In a non-Base plan, each field shows where its value comes from** — "From Base" or "Changed in this plan" — per the display in §4.4. Two consequences the Flutter developer must get right:

- **Save sends only the fields the user actually edited.** Echoing the whole resolved row back turns a partial override into a whole-item snapshot, which breaks the agreed behaviour in M1 R19 even against a correct backend. Acceptance case 25.11 fails on a client that echoes.
- **A field still marked "From Base" must visibly update** when Base changes, on next load. The user needs to see inheritance working, not just be told it does.

**Editing the same item in the Base Plan** shows no per-field origin labels — in Base there is nothing to inherit from.

### 6.3 C4 — Schedule picker

The highest-risk small component in the app. Contents:

- **Frequency:** One time · Weekly · Every 2 weeks · Monthly · Quarterly · Every 6 months · Yearly. Exactly seven, no custom option (D-08).
- **Start date.**
- **Ends:** Never · On date.
- **A plain-language summary line** that restates the rule: "Every month on the 25th, from 25 Jan 2026." For a start date of the 29th, 30th or 31st, the summary must add: "In shorter months, this falls on the last day." That sentence is the UI surfacing of the clamp rule in architecture §7.3, and it prevents the most common support question this product will get.

### 6.4 C5 — Remove / delete confirm

Copy is state-dependent and must be exact:

| Situation | Title | Body |
|---|---|---|
| Base, no dependents | Delete Rent? | This removes it from your Base Plan and every plan that inherits it. |
| **Base, with dependents** | **Delete Rent?** | **Rent is changed in 2 of your plans. Deleting it removes it from those plans as well, along with your changes.** |
| Non-Base, inherited | Remove Rent from Buy House? | Rent stays in your Base Plan. |
| Non-Base, scenario-only | Delete Mortgage? | This only exists in Buy House. |

The dependents row is new in v1.1 (M1 R20). Before showing this dialog for a Base item, the client calls `GET /v1/transactions/{id}/dependents` and uses the count to pick between the first two rows. Naming the affected plans is better than a bare count where there is room for it.

The deletion still proceeds — it is the user's own financial picture, and blocking it because of a plan made months ago would be worse. The warning exists so the consequence is not a surprise.

---

## 7. Forecast

### 7.1 D1 — Forecast

Maps to RFP §4.5 and §4.7. Highest complexity screen in Phase 1.

**Top:** horizon selector — 1 / 3 / 5 / 10 years (D3 or inline segmented control).

**Chart:** projected cash balance over time, monthly points. Tap a point → D2 month breakdown. Must stay legible at 120 points on a phone — expect thinned labels and a summarised x-axis at long horizons, and design for that explicitly rather than discovering it at 10 years.

**View toggle:** Balance · Income vs expenses · Net cash flow. Three views over one payload (RFP §4.7).

**Table below chart:** month · income · expenses · net · closing balance. Scrollable, sticky header. Annual grouping is a client-side sum of twelve monthly rows.

**API:** `GET /v1/scenarios/{id}/forecast?horizon=`. One call feeds chart, toggle views and table.

**States:** loading · empty (flat line at the Current Cash Balance, with an add-transaction prompt) · error.

**When the as-of date is in the past**, the chart begins at the as-of month, not at today. Months between the anchor and today are projections of months that have already passed, and must be visually distinguished from the future — a subtle background band, or a marker at the current month. Without that, the user reads settled history into what is actually an untested projection. `current_month` and `months_elapsed` in the payload tell the client exactly where to draw the line.

### 7.2 D2 — Month breakdown

Tap any month → sheet listing every transaction that contributed to it, with amounts, plus that month's income / expense / net / closing balance.

Not in the RFP. Recommended anyway, and cheap because the data is already resolved server-side. It is the screen that answers "why is this number what it is," and it converts the forecast from something the user is asked to believe into something they can audit. Directly supports RFP §10's reconciliation criterion during UAT.

---

## 8. Plans

### 8.1 E1 — Plans list

Base Plan pinned first, labelled, never deletable. Other plans as cards: name, created date, a one-line summary (projected balance at horizon), overflow → E6 actions. `[Create plan]` and `[Compare]` as primary actions.

**Archived plans** sit in a separate collapsed section at the bottom, with a count. Each offers **Restore** and **Delete**. They cannot be made active, compared or duplicated from here — restore first. The section is absent entirely when nothing is archived, rather than showing an empty heading.

### 8.2 E2 — Create plan

Name · optional current-balance override (amount only — the as-of date is shared across all plans) · a short explanation of what a plan is, shown on first use only: *"A plan starts as a copy of your assumptions. Change what you like — your Base Plan stays as it is, and anything you don't change keeps following it."*

That second clause matters as much as the first. Users understand "a copy"; what they do not expect is that the copy stays connected. One sentence at creation prevents most of the confusion the whole badge system exists to manage.

### 8.3 E3 — Plan detail

Summary of this plan's differences from Base — counts of added, modified and removed items, plus the projected balance difference at the default horizon. Actions: switch to this plan · compare with Base · rename · duplicate · archive · delete.

### 8.3.1 E6 — Plan actions, and the copy that must be exact

Archive and delete are one tap apart and one is permanent. The copy has to carry that difference on its own.

| Action | Label | Confirmation |
|---|---|---|
| Duplicate | Duplicate | None. Creates "Buy House (copy)", switches to it, offers an inline rename |
| Archive | Archive | "Archive Buy House? It stays saved and you can restore it any time." |
| Restore | Restore | None |
| Delete | Delete | "Delete Buy House permanently? Anything you added in this plan will be lost. This can't be undone." Destructive styling |

**What duplicating copies, in the interface.** The duplicate opens showing the same items with the same badges as the source — the same things marked From Base, Modified and Only in this plan. It is a copy of the user's *changes*, not a frozen snapshot of the figures, so it keeps following the Base Plan exactly as the source does (M1 R24–R26). If the user later changes their salary in Base, both plans move.

**Duplicating the Base Plan** is allowed and produces a plan where every item reads "From Base" and nothing reads "Only in this plan". A duplicate of Base showing two of everything is the defect M1 case 25.16 exists to catch, and it is visible at a glance in the UI.

**Archived plans keep following Base** (M1 R23). A plan archived before a raise shows the new salary when restored. Nothing in the UI needs to explain this, but the restore should land the user in the plan so they can see current figures rather than assume stale ones.

### 8.4 E4 — Compare setup

Plan A (defaults to Base) · Plan B · horizon. Both must be selected; a plan cannot be compared with itself.

### 8.5 E5 — Compare results

Maps to RFP §4.6.

1. **Headline delta** — difference in closing balance at the horizon, in amount and percent. Percent is suppressed (shown as "—") when the baseline is zero.
2. **Dual-line chart** — A and B, clearly distinguished by more than colour alone (line style or direct labels), because colour-only encoding fails for colour-blind users and prints badly in client decks.
3. **"What's driving this"** — the `drivers` payload rendered as a ranked list: each named transaction, whether it was added, modified or removed, and its contribution. This is the RFP's "clearly communicate which assumptions drive the difference," and it is our strongest visible differentiator. It deserves real design attention, not a footnote.
4. **Monthly table** — month · A · B · difference. Horizontal scroll on phone.

**API:** `GET /v1/forecast/compare?a=&b=&horizon=`.

---

## 9. Settings

F1 lists: Profile · Currency · Language · Current cash balance · Plans · Export data · Change password · Reset data · Delete account · About.

Three notes that affect design:

- **F5 Current cash balance** is not an ordinary setting. It shows the current figure with its as-of date and opens B3 to change it. Changing it re-anchors every projection in every plan, so it needs the preview and explicit confirm described in §5.3 — never a text field that saves on blur.
- **F3 Currency** requires a confirmation before changing, stating plainly that **amounts will not be converted** (M1 R31). "Your amounts stay the same — only the currency label changes. 25,000 SAR becomes 25,000 USD." Without this, a user will reasonably assume conversion happened and misread every figure in the app from then on. The confirm is cheap; the misunderstanding is not recoverable.
- **F8 Reset** and **F9 Delete account** are irreversible. Type-to-confirm, and the copy states exactly what is destroyed. Export (F7) should be offered inside the reset confirmation as the obvious alternative.

---

## 10. Copy rules

The interface's words are part of the design and are specified here so they stay consistent across 37 surfaces and two languages.

- **The two balances keep their names everywhere, without exception.** "Current cash balance" is only ever the user's confirmed figure. "Projected balance" is only ever an engine output. Never "your balance" for either, never "balance" alone as a column header, never "forecast balance" as a third variant. This is the one naming rule in the product with a signed rule behind it (M1 R1–R3), and inconsistency here undoes the visual separation the dashboard works to establish.
- **Name things by what the user controls.** "Plan," not "scenario overlay." "Schedule," not "recurrence rule." "Current cash balance," not "opening balance" — the user is telling us what they have now, not opening a ledger period. The user never sees our domain vocabulary.
- **Buttons say what happens.** "Save changes," not "Submit." "Remove from this plan," not "Delete."
- **An action keeps its name through the whole flow.** The button that says "Remove from this plan" produces a toast that says "Removed from Buy House."
- **Errors state what happened and what to do.** They do not apologise and they are never vague. "End date can't be before the start date" — not "Invalid input."
- **Empty screens are invitations, not apologies.** One sentence, one action.
- **Write for Arabic from the start.** English strings that only work as puns, clipped fragments or clever labels do not survive translation. Sentence case, plain verbs.
- **Never show raw server text.** Every message the user reads is a localized client string keyed off a server error code (architecture §10).

---

## 11. Direction for the designer

### 11.1 What the product is

A financial planning tool for adults in Saudi Arabia making real decisions with real money. Its job is to be **trusted**. It is not a gamified savings app and it should not borrow that visual language — no confetti, no streaks, no mascot. The nearest emotional register is a well-made professional instrument.

The one moment of genuine delight available is the forecast line extending into the future. That is the product's thesis made visible, and it is where visual investment should concentrate.

### 11.2 Type and numerals

Numbers are the content. The type system needs a face with **tabular figures** for all financial values so columns align in the forecast and compare tables. It must carry Arabic properly — a display face with no Arabic cut is not a candidate, and pairing a Latin face with a mismatched Arabic fallback is the most common way bilingual apps end up looking broken in one language.

**Decision needed from the client (§16 of the architecture doc, open question 6):** Western digits (0–9) or Eastern Arabic (٠–٩) in Arabic mode. Our default assumption is Western, standard in Saudi financial apps. Design both if the answer is delayed.

### 11.3 Charts under RTL

Flutter chart libraries do not mirror automatically. Two questions the designer must answer, because they change implementation cost:

1. Does the time axis mirror in Arabic (newest on the left, time flowing right-to-left)?
2. Do axis labels, tooltips and legends mirror independently of the plot area?

The common convention is a mirrored axis with Western digit labels. Whatever is chosen must be specified in the handoff, because it will not happen by accident.

### 11.4 States are the deliverable, not the happy path

Every list and data screen needs four designs: loading, empty, populated, error. The empty states matter disproportionately here — a brand-new user's first three screens are all empty, and that is the entire first impression.

### 11.5 Not in scope

Dark mode is not in the RFP and is not currently priced, and it remains unanswered at M1 close (architecture §16.2). Retrofitting a theme across 37 surfaces is far more expensive than accounting for it now, so this needs an answer before design starts rather than after. Also out: tablet layouts, landscape, illustration systems beyond simple empty-state art.

---

## 12. Designer deliverables

1. **Wireframes** — all 37 surfaces, LTR, greyscale.
2. **High-fidelity screens** — all 37, LTR, English, populated state.
3. **Key states** — loading / empty / error for B1, C1, D1, E5, plus B1 in its stale-balance state.
4. **Arabic RTL mirrors** — the 11 core surfaces: B1, B2, B3, C1, C2, C4, D1, D2, E1, E5, F1. Not all 37; these eleven prove every layout pattern in the app.
5. **Component library** — buttons, inputs, amount field, list rows, badges (the three plan-state badges), **per-field origin labels** (From Base / Changed in this plan), sheets, dialogs, chart styles, empty states.
6. **Clickable prototype** covering the flows in §4, including §4.4.
7. **Handoff:** spacing scale, type scale, colour tokens, icon set, chart specifications including the RTL decision from §11.3.

---

## 13. Estimation summary

| Area | Surfaces | Notes |
|---|---|---|
| Auth & onboarding | 9 | Standard patterns, low risk |
| Home | 3 | The heaviest screen in the product, plus the balance-update sheet |
| Transactions | 6 | Badge logic, per-field origin display and the schedule picker carry the risk |
| Forecast | 3 | Chart work at 120 data points, plus the elapsed-months band |
| Plans & compare | 6 | Compare results is the most complex screen |
| Settings | 10 | Mostly simple forms; two destructive flows and one currency confirm |
| **Total** | **37** | |

**Where the real effort sits, for sprint planning:**

1. **The two balances on the dashboard (B1)** — new in v1.1 and now the highest-value design problem in the product. A signed rule depends on users not confusing them.
2. **Per-field origin display (C2)** — correct inheritance looks like a bug without it, and it is the visible face of M1 case 25.11.
3. **The schedule picker (C4)** — including the shorter-months sentence.
4. **The forecast chart at long horizons (D1)** — 120 points on a phone, plus distinguishing elapsed months from future ones.
5. **Compare results (E5)** — particularly "What's driving this".
6. **RTL verification across all of it.**

Those six are worth more attention than the twenty simple screens combined.

---

## 14. Open questions

Full list and status in architecture §16. The ones that block or shape design work:

**Blocking — design cannot start without these:**

1. **Dark mode** — in or out.
2. **Eastern vs Western Arabic numerals** in Arabic mode.
3. **Chart axis mirroring** in RTL.

**Needed during design:**

4. **Outlook indicator** — what rules define improving / stable / declining. To be agreed with the client, not invented by us.
5. **Stale-balance threshold** — how old before the dashboard prompts. Proposing 30 days. Drives the B1 prompt and its copy.
6. **Onboarding step 3** — guided first income, or land on an empty dashboard.
7. **Plan limit** — cap per user? Affects the plans list, the compare picker and the duplicate flow.

**Design-adjacent, but ours to resolve rather than the client's:**

8. **Which balance leads on the dashboard** — the confirmed figure or the projected one. A real argument either way (§5.1); the designer should propose and we decide together rather than defaulting.
