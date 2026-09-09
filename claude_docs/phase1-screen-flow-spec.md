# Phase 1 — Screen Flow & UX Specification

**Status:** Draft v1.0 — for internal lock before design work begins
**Owner:** Nabeel Sohail (Technical Lead / Architect)
**Depends on:** `phase1-system-architecture.md` (domain model §4, API §9, overlay editing §9.2, localization §10)
**Audience:** UI/UX designer, Flutter developer, QA

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

**34 surfaces total: 24 full screens, 10 modals/sheets/dialogs.** This is the number to design against and to estimate against.

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
| A8 | Onboarding 2 — opening balance | Screen | M |
| A9 | Onboarding 3 — first income (skippable) | Screen | M |
| **B — Home** ||||
| B1 | Dashboard | Screen | **L** |
| B2 | Plan switcher | Sheet | S |
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
| F5 | Opening balance | Screen | M |
| F6 | Change password | Screen | S |
| F7 | Export data | Screen | S |
| F8 | Reset data | Dialog | M |
| F9 | Delete account | Dialog | M |
| F10 | About & legal | Screen | S |

The four **XL/L-heavy** screens — Dashboard, Transactions list, Forecast, Compare results — carry most of the product's value and most of its risk. They should be designed first and prototyped first.

---

## 4. Core flows

### 4.1 First launch

```
Splash → Welcome (pick العربية / English) → Register
   → Onboarding 1: currency (default SAR)
   → Onboarding 2: opening balance + "as of" date
   → Onboarding 3: add your income  [Skip]
   → Dashboard (Base Plan)
```

Onboarding 3 exists so the first Dashboard is not empty. A forecasting app whose first screen is a flat zero line teaches the user nothing. If skipped, the Dashboard shows a purposeful empty state (§5.1) rather than zeros.

Language is chosen **before** account creation, so registration itself is already localized.

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

### 4.5 Comparing

```
Plans → [Compare] → E4: pick Plan A (default: Base), Plan B, horizon
   → E5 results: chart with two lines, delta summary, "What's driving this",
     monthly table with A / B / difference
```

---

## 5. Home

### 5.1 B1 — Dashboard

Maps to RFP §4.2. The single most-viewed screen.

**Header:** plan chip (tappable → B2) · settings icon.

**Content, in priority order:**

1. **Current cash balance** — the hero figure. Opening balance carried to the current month's close.
2. **This month:** income · expenses · net cash flow. Net must be visually distinct from balance — these are the two figures users most often conflate, and RFP §4.2 explicitly calls for the distinction.
3. **Forecast balance** — projected balance at a stated future point, with the point named ("in 12 months"), never an unlabelled number.
4. **Outlook indicator** — a plain-language read of trajectory (improving / stable / declining), derived from the sign and slope of net cash flow across the forecast. Rules to be fixed with the client in discovery; it must be defensible, not vibes.
5. **Mini balance chart** — 12 months, tappable → Forecast tab.
6. **Quick add** button.

**API:** `GET /v1/scenarios/{active}/forecast?horizon=12`. One call. Everything above is read from that payload.

**States:**
- *Loading* — skeletons in the shape of the real content, not a centred spinner.
- *Empty* (no transactions) — not zeros. A direct invitation: "Add your income to see your forecast." One primary action.
- *Error* — inline retry, previous data retained if present.

**RTL:** amount + currency ordering follows locale; the mini chart's time axis direction is a decision flagged in §11.3.

### 5.2 B2 — Plan switcher (sheet)

List of plans, active one marked, Base always first and labelled. "Create plan" at the bottom. Archived plans are not listed here. Selecting switches context app-wide and returns to the current tab.

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
| Non-Base, inherited | Remove Rent from Buy House? | Rent stays in your Base Plan. |
| Non-Base, scenario-only | Delete Mortgage? | This only exists in Buy House. |

---

## 7. Forecast

### 7.1 D1 — Forecast

Maps to RFP §4.5 and §4.7. Highest complexity screen in Phase 1.

**Top:** horizon selector — 1 / 3 / 5 / 10 years (D3 or inline segmented control).

**Chart:** projected cash balance over time, monthly points. Tap a point → D2 month breakdown. Must stay legible at 120 points on a phone — expect thinned labels and a summarised x-axis at long horizons, and design for that explicitly rather than discovering it at 10 years.

**View toggle:** Balance · Income vs expenses · Net cash flow. Three views over one payload (RFP §4.7).

**Table below chart:** month · income · expenses · net · closing balance. Scrollable, sticky header. Annual grouping is a client-side sum of twelve monthly rows.

**API:** `GET /v1/scenarios/{id}/forecast?horizon=`. One call feeds chart, toggle views and table.

**States:** loading · empty (flat line at opening balance, with an add-transaction prompt) · error.

### 7.2 D2 — Month breakdown

Tap any month → sheet listing every transaction that contributed to it, with amounts, plus that month's income / expense / net / closing balance.

Not in the RFP. Recommended anyway, and cheap because the data is already resolved server-side. It is the screen that answers "why is this number what it is," and it converts the forecast from something the user is asked to believe into something they can audit. Directly supports RFP §10's reconciliation criterion during UAT.

---

## 8. Plans

### 8.1 E1 — Plans list

Base Plan pinned first, labelled, never deletable. Other plans as cards: name, created date, a one-line summary (balance at horizon), overflow → E6 actions. Archived section, collapsed. `[Create plan]` and `[Compare]` as primary actions.

### 8.2 E2 — Create plan

Name · optional starting-balance override · a short explanation of what a plan is, shown on first use only: *"A plan is a copy of your assumptions you can change freely. Your Base Plan stays as it is."* This one sentence prevents most of the confusion the whole badge system exists to manage.

### 8.3 E3 — Plan detail

Summary of this plan's differences from Base — counts of added, modified and removed items, plus the balance difference at the default horizon. Actions: switch to this plan · compare with Base · rename · duplicate · archive · delete.

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

F1 lists: Profile · Currency · Language · Opening balance · Plans · Export data · Change password · Reset data · Delete account · About.

Two notes that affect design:

- **F5 Opening balance** is not an ordinary setting. Changing it moves every number in the app. It needs a preview of the effect and an explicit confirm, not a text field that saves on blur.
- **F8 Reset** and **F9 Delete account** are irreversible. Type-to-confirm, and the copy states exactly what is destroyed. Export (F7) should be offered inside the reset confirmation as the obvious alternative.

---

## 10. Copy rules

The interface's words are part of the design and are specified here so they stay consistent across 34 surfaces and two languages.

- **Name things by what the user controls.** "Plan," not "scenario overlay." "Schedule," not "recurrence rule." The user never sees our domain vocabulary.
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

Dark mode is not in the RFP and is not currently priced. Flag it to the client before design begins rather than after: retrofitting a theme across 34 surfaces is far more expensive than accounting for it now. Also out: tablet layouts, landscape, illustration systems beyond simple empty-state art.

---

## 12. Designer deliverables

1. **Wireframes** — all 34 surfaces, LTR, greyscale.
2. **High-fidelity screens** — all 34, LTR, English, populated state.
3. **Key states** — loading / empty / error for B1, C1, D1, E5.
4. **Arabic RTL mirrors** — the 10 core surfaces: B1, B2, C1, C2, C4, D1, D2, E1, E5, F1. Not all 34; these ten prove every layout pattern in the app.
5. **Component library** — buttons, inputs, amount field, list rows, badges (the three plan-state badges), sheets, dialogs, chart styles, empty states.
6. **Clickable prototype** covering the flows in §4, including §4.4.
7. **Handoff:** spacing scale, type scale, colour tokens, icon set, chart specifications including the RTL decision from §11.3.

---

## 13. Estimation summary

| Area | Surfaces | Notes |
|---|---|---|
| Auth & onboarding | 9 | Standard patterns, low risk |
| Home | 2 | One heavy screen |
| Transactions | 6 | Badge logic and schedule picker carry the risk |
| Forecast | 3 | Chart work at 120 data points |
| Plans & compare | 6 | Compare results is the most complex screen |
| Settings | 10 | Mostly simple forms; two destructive flows |
| **Total** | **34** | |

**Where the real effort sits, for sprint planning:** the schedule picker (C4), the three-state badge system across C1/C2/C5, the forecast chart at long horizons (D1), the compare results screen (E5), and RTL verification across all of it. Those five items are worth more attention than the twenty simple screens combined.

---

## 14. Open questions

Carried into the discovery workshop alongside the architecture doc's §16:

1. **Dark mode** — in or out? Decide before design starts.
2. **Eastern vs Western Arabic numerals** in Arabic mode.
3. **Chart axis mirroring** in RTL.
4. **Outlook indicator** — what rules define improving / stable / declining? Must be agreed, not invented by us.
5. **Password reset** requires a transactional email provider. Not mentioned in the RFP; confirm it is in scope and who pays for the service.
6. **Onboarding step 3** — is a guided first-transaction step wanted, or should users land straight on an empty dashboard?
7. **Plan limit** — cap the number of plans per user? Affects the Plans list and the compare picker.
