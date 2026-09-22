# Milestone 1 — Discovery & Specification

**Personal Financial Management & Forecasting Application — Phase 1**

**Final — incorporating all agreed clarifications**

Prepared for: [Client Name]
Prepared by: [Company Name]
Date: [Date]
Version: 1.1 — for signature

---

## Contents

**Part 1 — Specification** (sections 1 to 14)
What we are building, how it works, what is and is not included, and what we need from you.

**Part 2 — Agreed Financial Rules & Test Cases** (sections 15 to 33)
The financial rules the application must follow, and the specific test cases that prove them. This is the objective reference for development, automated testing and final acceptance.

Both parts are signed together as the agreed specification for Phase 1.

---

## Revision note

This version incorporates the six clarifications raised in your red-team review, and the agreed separation of Current Cash Balance from Projected Balance.

| Change | Where |
|---|---|
| Current Cash Balance and Projected Balance defined as separate figures | §3.1, §5.2, R1–R3, cases 18.3–18.5 |
| Dashboard supports a selected period, not only the current month | §5.2, R32–R33, case 27.3 |
| Archive behaviour defined in full | §3.3, R22–R23, case 25.17 |
| Duplicate behaviour defined; inheritance and overrides preserved | §3.3, R24–R26, cases 25.15–25.16 |
| Inheritance behaviour after a Base Plan item is changed or deleted | §3.3, R19–R21, cases 25.10–25.14 |
| Test suite and execution results confirmed as Phase 1 deliverables | §9.2 |
| Currency confirmed to perform no conversion | §6, R30–R31, case 28.1 |

---

# PART 1 — SPECIFICATION

---

## 1. What this document is for

This document sets out exactly what we understood from your RFP, exactly what we will build in Phase 1, and exactly what we will not build.

It has three jobs:

1. **Confirm we understood you correctly.**
2. **Agree the boundary of Phase 1.** A fixed price needs a fixed scope. Section 9 lists what is included, section 10 lists what is not.
3. **Record the agreed financial rules.** Part 2 is the objective reference against which the software is built, tested and accepted.

You do not need a technical background to read this. There is nothing here about code or databases. If you would like this document in Arabic, we are happy to provide it.

---

## 2. What we are building, in one paragraph

A mobile app for iPhone and Android, in Arabic and English, that lets a person record their income and expenses, see a projection of their cash balance for up to ten years ahead, create alternative plans such as "what if I buy a house," and compare those plans side by side to see which leaves them better off.

Your RFP's product philosophy is **Track → Understand → Forecast → Simulate → Decide.** Phase 1 builds the reliable foundation: recording your financial picture, projecting it forward accurately, and comparing alternatives. Phase 2 adds the intelligence layer on top.

---

## 3. How the app works

### 3.1 Your financial picture

The app holds three things about you.

**Your current cash balance.** How much cash you have right now, as you have entered it. This figure is yours — you enter it and you confirm it. **Nothing in the application ever changes it automatically.** Scheduled income and expenses do not adjust it. The passage of time does not adjust it.

Because it is a figure confirmed at a moment, it carries the date it was confirmed. The app always shows it with that date: *"SAR 45,000 — as of 1 January 2026."* Your projection is built forward from that point.

When your real balance changes and you want the app to reflect it, you update the figure and the date moves with it. Your projection is then rebuilt from the new, confirmed position. **Updating your balance is how you keep the app aligned with reality in Phase 1.**

If your balance has not been confirmed for a while, the app invites you to update it. Without that reminder a projection would keep building on an increasingly old figure with nothing on screen to indicate it.

We should be plain about what this does and does not achieve. It guarantees the app never shows you a balance it cannot stand behind, because every balance shown is one you confirmed yourself. It cannot detect when your real spending diverges from your plan — nothing in a planning-only product can. Confirming actual transactions is what Phase 2 addresses.

**Your income.** Salary, bonuses, rental income — anything that comes in.

**Your expenses.** Rent, utilities, subscriptions, loan payments, school fees — anything that goes out.

### 3.2 One-time and repeating items

Every income or expense is either **one-time** or **repeating**.

A one-time item happens once on a specific date — a bonus in December, a car repair in March.

A repeating item happens on a schedule. You choose from: weekly, every two weeks, monthly, quarterly, every six months, or yearly. You set a start date, and optionally an end date if it stops at some point — a car loan finishing in three years, for example.

One useful detail: if you set something to repeat monthly on the 31st, the app places it on the last day of any shorter month. A payment on the 31st of January falls on the 28th of February, then returns to the 31st of March. The app explains this on screen when you choose such a date.

### 3.3 Plans

This is what makes the product a decision tool rather than a budget tracker.

**Your Base Plan is your real life as it stands today.** Your actual salary, your actual rent, your actual commitments. This is where you start and where you will spend most of your time.

**A new plan is a version of your life where something is different.** You might create one called "Buy House." When you create it, it begins as your real life — everything from your Base Plan is already in it. You then change only what would actually be different: add a mortgage payment, add a down payment as a one-time expense, and set an end date on your current rent because you would stop paying it once you move.

Everything you did not touch stays connected to your Base Plan. **If your salary increases, you update it once in your Base Plan and every alternative plan updates automatically.** You never maintain the same information in several places, and your plans never quietly go out of date.

Your Base Plan is never changed by anything you do inside another plan.

#### Changing an item inside a plan

When you change an item inside a plan, the app records **only the specific fields you changed** — not a whole copy of the item.

An example. Your Base Plan rent is SAR 4,500 monthly with no end date. In your "Buy House" plan you change only the end date, to 31 May. You never touched the amount.

Your landlord then raises the rent, and you update your Base Plan to SAR 5,000.

Your "Buy House" plan now shows **SAR 5,000, ending 31 May.** The amount follows your Base Plan, because you never overrode it. The end date stays yours, because you did.

The alternative — treating a change as a complete snapshot of the item — would leave that plan showing SAR 4,500 permanently, with nothing on screen to tell you it was out of date.

In the app, a changed item shows which specific fields differ from your Base Plan, and offers a single action to return it fully to Base.

#### Removing an item inside a plan

Removing an item within a plan removes it from that plan entirely — every occurrence, across the whole projection.

**This matters in practice.** If you want an item to continue for a while and then stop — paying rent until you move in June — you should **change** the rent to add an end date, not **remove** it. Removing it takes it out of the plan from the very first month. Both behaviours are correct and both are useful; the app makes the difference clear. Cases 25.4 and 25.5 demonstrate each.

#### When a Base Plan item is changed or deleted later

| State inside your alternative plan | You change it in your Base Plan | You delete it from your Base Plan |
|---|---|---|
| **Unchanged** | The plan shows the new values immediately | The item disappears from the plan |
| **Changed** | Fields you changed keep your values. Fields you did not change take the new Base values | The item disappears from the plan. Your change is discarded with it |
| **Removed** | No visible effect — the item remains absent | No visible effect — the item remains absent |

**You are warned before deleting.** If a Base Plan item is changed or removed in any of your plans, the confirmation tells you: *"Rent is changed in 2 of your plans. Deleting it will remove it from those plans as well."*

If you later add a new item with the same name, it is a new item. Plans inherit it fresh, with no changes carried over from the deleted one.

#### Archiving a plan

Archiving puts a plan aside without losing anything.

- The plan is retained in full — its additions, its changes and its removals.
- It is removed from the active plans list and appears in a separate **Archived** section.
- It can be restored at any time, complete and unchanged.
- If it was the plan you were viewing, the app returns you to your Base Plan.
- While archived it cannot be your active plan and does not appear in the comparison picker.
- Archived plans do not count toward any limit on the number of plans.
- Your Base Plan cannot be archived.

**An archived plan keeps inheriting from your Base Plan while it is archived.** If you archive a plan, then raise your salary in your Base Plan, then restore the plan six months later, the restored plan shows your **new** salary. A restored plan displaying a salary you no longer earn would be misleading, with no way for you to tell.

Archiving is reversible and destroys nothing. Deleting a plan is permanent and requires explicit confirmation.

#### Duplicating a plan

**Duplicating copies your changes, not the resulting figures.**

The new plan receives copies of every change you made, every removal you made, and every item that exists only in the source plan — together with its own live connection to your Base Plan.

The duplicate is a **sibling** of the source plan, not a copy underneath it:

- Changing your **Base Plan** affects both.
- Changing the **source plan** does not affect the duplicate.
- Changing the **duplicate** does not affect the source plan.

A duplicate is a copy of your *changes*, not a photograph of what you were looking at. If your Base Plan has gained a new item since the source plan was created, both plans show it, because both inherit live.

**Duplicating your Base Plan** is allowed and gives you a clean new plan that inherits everything with no changes. Each item appears once, not twice.

The duplicate is named after the source with a suffix, such as "Buy House (copy)", and can be renamed immediately. Archived plans must be restored before they can be duplicated.

### 3.4 The forecast

Once your income and expenses are in, the app projects forward month by month from your confirmed balance. For each month it shows how much comes in, how much goes out, the difference, and your projected balance at the end of that month.

You can look ahead one year, three years, five years or ten years.

You can also tap any month to see exactly which items produced that figure. A forecast you can inspect is a forecast you can trust; if a number ever looks wrong, you can see the reason immediately.

### 3.5 Comparing plans

You pick two plans and a period, and the app shows you:

- The difference in projected balance at the end of the period, in riyals and as a percentage
- A chart with both plans drawn together
- A month-by-month table showing both plans and the difference
- **A plain list of what is causing the difference** — for example, that the mortgage costs SAR 45,500 more over the period, while rent ending early saves SAR 31,500

That last item is the part you are likely to use most. A chart tells you *that* two plans differ. This tells you *why*, item by item, and the individual figures add up to the total difference exactly.

---

## 4. Walking through it as a user would

**Setting up.** Ahmed downloads the app and chooses Arabic. He creates an account, confirms his currency is Saudi Riyal, and enters his current cash balance of SAR 45,000. The app records it as of today. He adds his salary of SAR 25,000, monthly, from the 25th. He lands on the home screen and already sees a projection.

**Building the picture.** Over a few minutes he adds rent, utilities, school fees, his car loan with its end date in two years, and two subscriptions. The home screen updates as he goes.

**Looking ahead.** He opens the forecast and selects five years. His projected balance climbs steadily, with a visible step up in two years when the car loan ends. He taps that month and sees the loan has indeed dropped off.

**Trying a decision.** Ahmed is considering buying a house. He creates a plan called "Buy House." Everything is already there. He adds a down payment of SAR 300,000 next June, adds a mortgage of SAR 6,500 monthly from the same month, and sets his rent to end in May. The app confirms his Base Plan rent is untouched.

**Deciding.** He compares "Buy House" against his Base Plan over ten years. He sees where the down payment takes his balance down, how long it takes to recover, and where the two lines cross. The list underneath tells him the mortgage costs SAR 780,000 over ten years while ending his rent saves SAR 504,000. He now has a number instead of a feeling.

**Life changes.** Six months later Ahmed gets a raise. He updates his salary once, in his Base Plan. All his plans reflect it immediately.

**Staying aligned.** At the same time he notices his balance is still dated from six months ago. He checks his bank, enters his actual figure, and his projection rebuilds from that confirmed position.

---

## 5. What is in the app

Around **34 screens and panels**, in six areas.

### 5.1 Getting started

Language selection, sign up, sign in, password reset, and a short setup asking for your currency, your current cash balance, and your first income.

### 5.2 Home

The home screen shows two balance figures, deliberately separate and clearly labelled:

**Current Cash Balance** — the figure you entered and confirmed, shown with the date you confirmed it. Nothing changes it automatically.

**Projected Balance** — calculated by the forecasting engine from your Current Cash Balance plus your scheduled income and expenses.

Keeping these separate is important. The first is something you know. The second is something the app has worked out. Presenting them as one number would blur that line, and in Phase 1 the app has no way to confirm whether a scheduled payment actually arrived.

The home screen also carries a **period selector**: this month, next 3 months, next 6 months, next 12 months. Some figures respond to it and some do not:

| Figure | Responds to period? |
|---|---|
| Current Cash Balance | No — it is your position now |
| Income | Yes — total across the period |
| Expenses | Yes — total across the period |
| Net cash flow | Yes — income minus expenses across the period |
| Projected Balance | Yes — your projected balance at the end of the period |
| Outlook indicator | Yes — assessed across the period |

Periods look forward only and always begin with the current month. Phase 1 holds no record of actual past transactions, so a past period would show only a projection of a month that has already happened. Backward-looking periods become meaningful in Phase 2.

The home screen is also where you switch between plans, and where you are prompted to update your balance if it has not been confirmed for a while.

### 5.3 Income and expenses

The full list, grouped by income and expense, with search and filtering. Adding or editing an item covers name, amount, category, schedule and optional notes. Within a plan, each item shows whether it comes from your Base Plan, has been changed, or exists only in this plan.

### 5.4 Forecast

The projection as a chart and as a month-by-month table, with one, three, five and ten year views, three chart views (projected balance, income against expenses, and net cash flow), and the ability to open any month and see what is inside it.

### 5.5 Plans

Create, rename, duplicate, archive, restore and delete plans. See what makes each plan different from your Base Plan. Compare any two plans.

### 5.6 Settings

Profile, currency, language, current cash balance, password, data export, data reset, account deletion.

---

## 6. Arabic and English

Both languages are in the app from the first release, in a single app rather than two versions.

- Arabic reads right to left throughout — not only the text, but the whole layout, including menus, forms and navigation.
- Language is chosen before you create an account, so nothing is ever shown in the wrong language.
- Language can be changed at any time in settings and takes effect immediately.
- Dates, numbers and currency are formatted correctly for the chosen language.
- Charts and tables work properly in both directions.
- A third language can be added later by supplying translations, without redevelopment.

### Currency

**You select one currency, and changing it never converts your amounts.**

- Every amount in the app is displayed in your selected currency.
- Changing the currency changes the currency label and number formatting only. **The numbers themselves are never altered.** An amount entered as 10,000 in Saudi Riyals reads 10,000 after switching to US Dollars.
- The app contains no exchange rates and no conversion of any kind.
- Amounts cannot be held in more than one currency at the same time.

When you change currency after entering financial data, the app shows a confirmation stating plainly that amounts will not be converted. Without it, a user could reasonably assume conversion had occurred and misread every figure afterwards.

Multi-currency support and conversion belong in Phase 2 if you want them.

### Two things we need from you on language

**Arabic numerals.** Whether Arabic mode should use Arabic-Indic numerals (٠١٢٣) or Western numerals (0123). Most Saudi financial apps use Western, which is our default assumption.

**Arabic review.** The Arabic wording needs review by an Arabic speaker on your side before release. A mistranslated label in a financial app is a serious matter, and we would rather it be checked by someone who represents you than assumed correct by us.

---

## 7. How we make sure the numbers are right

Your RFP asks how we ensure the calculation engine is accurate and testable.

**The calculation is built as a separate, self-contained piece of software.** It is not mixed into the app screens or the database. It takes your financial information in and produces the projection out, and it has no other job. It can therefore be tested completely on its own, before it is connected to anything.

**It is built first.** Before any screen exists, before the app can even be logged into, the calculation engine is finished and tested. It is the part of the project that matters most, so it is built when there is the most time to get it right.

**The same information always produces the same answer.** There is no randomness and nothing that varies by when a calculation runs. Any result can be reproduced exactly, which matters when you are checking our work.

**It is tested against every case in Part 2 of this document**, including the awkward ones: payments on the 31st in February, yearly payments dated 29 February, weekly payments in months containing five of them, items ending mid-year, items that started before you began using the app.

**Every projection is automatically checked to balance.** The software confirms that the final projected balance equals your confirmed current balance plus every single item in between. If a projection ever failed to add up, the software would refuse to build.

**All calculations happen in one place, on the server.** Not partly in the app and partly on the server, which is a common source of figures that disagree with one another. One calculation, one answer, wherever it appears.

**Your own test cases.** Your RFP refers to independently verified test cases. Please share them. We will build them directly into our automated testing, which means that by handover your own cases will have been passing on every build for months. Acceptance then confirms a known result rather than discovering a new one.

---

## 8. How Phase 2 builds on this without rework

Your RFP asks how Phase 1 is structured so that Phase 2 does not require rebuilding it.

The calculation engine works on a simple principle: it accepts a list of dated amounts and works out the running balance. It does not care where those amounts came from. Every Phase 2 feature can therefore be added by feeding the same engine rather than replacing it.

**Financial events** — buying a house, taking a loan, planning a trip — become shortcuts that produce ordinary income and expense items. A house purchase becomes a down payment, plus a monthly mortgage, plus annual insurance. The engine treats these exactly like anything you entered by hand.

**What-if analysis** is a plan created automatically from one of those events, then forecast and compared using machinery that already exists in Phase 1.

**Best, expected and worst case** projections are the same engine run three times with different assumptions. We are building the place where those assumptions connect during Phase 1, deliberately doing nothing, so Phase 2 has somewhere to plug in.

**Inflation and salary growth** adjust amounts before the engine totals them. A single, contained addition.

**The AI assistant** suggests changes and answers questions but never calculates anything itself. It proposes; the same tested engine computes. Your RFP requires exactly this, and structuring it this way makes it a genuine guarantee rather than a promise.

**Confirming actual transactions and multiple accounts** are additions to the existing structure, not replacements for it. The Current Cash Balance already exists as a confirmed figure with a date; Phase 2 extends how that confirmation happens.

Every Phase 2 feature either feeds the engine or reads its output. Nothing reaches into the middle and changes how it works.

---

## 9. What is included in Phase 1

### 9.1 Product

| Area | What you get |
|---|---|
| **Accounts** | Sign up, sign in, password reset, profile, secure sessions |
| **Setup** | Language, currency, current cash balance, first income |
| **Home** | Current Cash Balance with its date, selected-period income, expenses and net, Projected Balance, outlook indicator, 12-month chart, plan switching, balance update prompt |
| **Income and expenses** | Add, edit, delete; one-time and repeating; categories; notes; start and end dates; search and filter |
| **Plans** | Create, rename, duplicate, archive, restore, delete; live inheritance from Base; field-level changes; isolation from Base |
| **Forecast** | Monthly projection over 1, 3, 5 and 10 years; income, expenses, net and projected balance; month-by-month breakdown |
| **Comparison** | Two plans side by side; chart; monthly table; difference in amount and percentage; explanation of what drives the difference |
| **Charts** | Projected balance over time, income against expenses, net cash flow, plan comparison; monthly and annual summaries |
| **Languages** | Arabic and English, full right-to-left support, one app |
| **Settings** | Currency, profile, language, current cash balance, plan management, data export, data reset, account deletion |
| **Platforms** | iPhone and Android |

### 9.2 Deliverables

- Product discovery and this agreed specification
- UX/UI wireframes and high-fidelity designs
- Clickable prototype, approved before development begins
- Mobile application for iOS and Android
- Backend APIs and database
- Forecasting and calculation engine
- Plans and comparison functionality
- **The automated financial test suite**, as source code forming part of the codebase you own
- **A test execution report** at handover, stating every case with its result, the total count and outcome, the exact software version tested identified by commit reference, the date and time of execution, and the code coverage of the calculation engine
- **The automated execution history**, demonstrating the suite ran on every change throughout the project rather than only at the end
- **A traceability table** mapping each acceptance criterion in RFP section 10 to the specific test cases that prove it
- QA and UAT support
- App Store and Google Play deployment support
- Source code and technical documentation
- Deployment and handover documentation

Your own test cases, once provided, are built into the same suite and appear in the same report, treated no differently from ours.

Because the test suite is yours and lives with the code, the financial rules agreed in this document remain enforced by software for the life of the product. Any future change — by us, by you, or by another vendor — that breaks an agreed rule is caught automatically rather than found by a user.

---

## 10. What is not included in Phase 1

This is the most important section for both of us. Everything below is genuinely useful and most of it belongs in Phase 2. None of it is in the Phase 1 price. If any item here is something you consider essential for the first release, tell us now — a straightforward conversation today, a difficult one in three months.

**Bank connection.** The app does not connect to your bank.

**Confirming actual transactions.** Phase 1 is a planning tool. You describe what you earn and spend, and the app projects it forward. It does not ask you to confirm each payment as it happens, and it does not compare what you planned against what actually occurred. You keep the app aligned with reality by updating your Current Cash Balance, as described in section 3.1.

**Multiple accounts.** Phase 1 works with a single overall cash position rather than separate current, savings and investment accounts with transfers between them.

**Currency conversion.** One currency, no conversion.

**Offline use.** The app requires an internet connection. This is a deliberate consequence of running every calculation in one place, which is what guarantees the figures always agree.

**Notifications and reminders.**

**Fingerprint or Face ID login.** Built so this can be added later without rework, but not built in Phase 1.

**Budgets and spending limits.**

**Loan schedules and amortisation tables.**

**Investments, assets and net worth tracking.**

**Financial health scores, financial freedom planning and automated recommendations.** Named in your RFP as Phase 2.

**AI assistant.** Phase 2.

**What-if analysis and financial events.** Phase 2.

**Dark mode.** Not mentioned in the RFP and not currently priced. Best decided before design begins — adding a second visual theme across 34 screens later is considerably more expensive than accounting for it now.

**Tablet and web versions.** Phone layouts only.

**Hijri calendar.** Our understanding is that this is not required. Please confirm, as it is easier to plan for now than to add later.

---

## 11. Decisions still outstanding

The clarifications from your review are settled. These remain open. The first three are needed before design begins, which means before M2 can start.

### Needed before M2

**1. Dark mode — in or out?**
*Our recommendation:* not in Phase 1.

**2. Arabic numerals — ٠١٢٣ or 0123?**
*Our recommendation:* Western numerals, consistent with most Saudi financial applications.

**3. In Arabic, should charts read right to left, with the most recent month on the left?**
*Our recommendation:* yes, matching the reading direction. This affects how charts are built and cannot be changed cheaply later.

### Needed during M2

**4. What should the outlook indicator say, and when?**
Your RFP calls for a simple financial outlook indicator. We suggest three states — improving, stable, declining — based on the direction of net cash flow across the selected period. We would like to agree the exact rule with you rather than invent it, since it is the app making a judgement about a user's finances.

**5. How often should the app prompt a user to confirm their Current Cash Balance?**
*Our recommendation:* when the confirmed date is more than 30 days old. Too frequent becomes noise; too rare and projections build on stale figures.

**6. Should there be a limit on the number of plans per user?**
*Our recommendation:* a generous limit, around twenty, to keep the plan list and comparison picker usable.

**7. Should new users be guided through adding their first income during setup, or land on an empty home screen?**
*Our recommendation:* guided, with a skip option.

### Needed before development

**8. Does your personal financial data need to be stored inside Saudi Arabia?**
A question for your legal advisers. Saudi data protection regulations place conditions on where personal data is held and on transferring it abroad. The answer determines where we host the system and affects the monthly running cost.

**9. Password reset requires an email service.** Not mentioned in the RFP but necessary for the sign-in feature you asked for. Inexpensive. We need to know which provider you would like to use and confirm it is in scope.

**10. Which analytics platform would you prefer?**
Your RFP asks for our recommendation. Firebase Analytics is free and standard for mobile. Alternatives exist if you would prefer to own the data more directly. This also affects what your privacy policy must say.

### At your convenience

**11. Your independently verified test cases.** Section 30 provides a template. The earlier we receive them, the earlier they are protecting the calculation engine on every build.

---

## 12. What we need from you to start

### Please start these immediately — they have the longest lead times

**Apple Developer Program enrollment** for your organisation. This requires a D-U-N-S number for your company, which can itself take one to two weeks to obtain, followed by Apple's own verification. It affects nothing until the very end of the project, at which point it prevents release entirely. It is the most common cause of delay in mobile projects, and starting it now removes the risk.

**Google Play Console** developer account.

**Domain name** for the service, if you do not already have one.

### Also needed

- Hosting account in your organisation's name, with access granted to us
- Domain and DNS access, or a named contact who can make DNS changes within two working days
- App name in Arabic and English
- Logo and brand materials, if they exist
- Privacy policy and terms of service from your legal adviser, before store submission
- A support email address, required by both app stores

### People

**One person with authority to approve.** Design and specification approvals that go through a committee are the main reason fixed-price projects slip.

**An Arabic-speaking reviewer** for testing before release.

**An agreed response time for approvals** — we suggest three working days.

### Ownership

Every account is registered in your name, with access granted to us. Nothing needs transferring at the end of the project; we hand over and our access is removed. This matches the ownership terms in your RFP.

---

## 13. How we will work

**M1 — Discovery & Specification.** This document, agreed and signed. Everything afterwards is measured against it.

**M2 — Design.** Wireframes, then full designs, then a clickable prototype you can hold and try before development starts. Approval matters here, because changing a design is inexpensive and changing a built app is not.

**M3 onward — Development.** The calculation engine is built and tested first, before any screens. You will see regular working builds on your own device rather than waiting until the end.

**Testing and release.** Your testing period, then submission to both stores, then handover of all source code, documentation and test results.

**Changes.** Anything not in this document is a change request with its own cost and timeline impact. This is what makes a fixed price possible, and it protects you as much as us. Small clarifications are simply handled; new features are quoted.

---

## 14. Defects

Any behaviour of the delivered application that disagrees with an agreed financial rule in section 17, or with the expected result of an agreed test case in sections 18 to 29, is a **defect**.

Correcting such a defect falls within the agreed Phase 1 scope and carries no additional cost or timeline impact.

Where a case in this document is found to be incorrect, or where a rule needs to change after agreement, that is handled as a specification change rather than a defect, and both parties agree the revision in writing.

---

# PART 2 — AGREED FINANCIAL RULES & TEST CASES

---

## 15. Purpose of Part 2

This part is the objective reference for every financial calculation in the product. It contains:

- **Section 17 — the agreed financial rules.** How the application treats balances, dates, repetition, month ends, leap years, plans, comparison and currency.
- **Sections 18 to 29 — the agreed test cases.** Specific inputs with their exact expected results.

Once signed, this part is used in three ways:

1. **As the development reference.** Developers build to these rules, not to interpretation.
2. **As the automated testing reference.** Every case below is built into our automated test suite and runs on every change to the software for the life of the project. A change that breaks any case cannot be released.
3. **As the acceptance reference.** Final acceptance is confirmed against this part, supported by the test execution report and traceability table described in section 9.2.

---

## 16. How to read a test case

Each case gives a current cash balance, a list of items, a forecast start month and a length, followed by the exact result the application must produce.

- All amounts are Saudi Riyals. Whole riyals are used for readability.
- Amounts are always entered as positive numbers. Whether something adds to or subtracts from your balance is determined by whether it is income or an expense.
- Dates are written as day-month-year.
- "Forecast start" is the first month of the projection.
- "Projected balance" is the calculated cash position at the end of that month.

---

## 17. The agreed financial rules

The test cases exist to prove these rules. If a rule here is not what you intended, the rule is the important part — the cases follow from it.

### Balances

**R1.** The **Current Cash Balance** is a figure the user enters and confirms. It carries the date on which it was confirmed, and that date is always displayed alongside it. **Nothing in the application changes it automatically** — not a scheduled income or expense, not the passage of time.

**R2.** The forecast is anchored to the confirmed date. The first month of the projection is the month containing that date. When the user updates their Current Cash Balance, the anchor moves and the projection is rebuilt from the new confirmed position.

**R3.** The **Projected Balance** is calculated by the forecasting engine from the Current Cash Balance plus scheduled income and expenses. It is always presented as a figure distinct from, and separately labelled to, the Current Cash Balance.

**R4.** Income increases the projected balance. Expenses decrease it. All amounts are entered as positive figures.

**R5.** For each month: projected closing balance equals the previous month's projected closing balance, plus that month's income, minus that month's expenses. For the first month, the previous balance is the Current Cash Balance.

**R6.** A projected balance may go negative, and is shown as a negative figure. The application does not stop at zero and does not hide a shortfall. Showing a future shortfall is one of the main purposes of the product.

### One-time items

**R7.** A one-time item occurs exactly once, in the month of its date, and only if that date falls within the forecast period.

### Repeating items

**R8.** A repeating item occurs first on its start date, and then at its chosen frequency.

**R9.** The start date is included. The end date is included — if an item's end date falls exactly on the day of an occurrence, that occurrence happens.

**R10.** An item with no end date continues to the end of the forecast period.

**R11.** Occurrences dated before the first month of the forecast are not included. The Current Cash Balance already reflects everything before it.

### Month ends

**R12.** For monthly, quarterly, half-yearly and yearly items, the day of the month is taken from the start date. In any month too short to contain that day, the occurrence falls on the last day of that month.

**R13.** The day of the month never drifts. It is always taken from the original start date, never from the previous occurrence. An item starting on 31 January occurs on 28 February and then returns to 31 March.

### Leap years

**R14.** February has 29 days in a leap year and 28 otherwise. An item anchored to 29 February occurs on the 28th in non-leap years and on the 29th whenever the year is a leap year.

### Weekly items

**R15.** Weekly and fortnightly items are placed on their real dates. A month may contain four or five weekly occurrences, or two or three fortnightly ones. The application does not convert these into a monthly average.

### Plans — inheritance

**R16.** A new plan inherits every item from the Base Plan. Any item not changed within a plan always reflects the current value in the Base Plan.

**R17.** Changing, adding or removing anything inside a plan never alters the Base Plan.

**R18.** Removing an item within a plan removes it from that plan entirely — every occurrence, across the whole forecast period.

**R19.** A change made inside a plan is recorded **field by field**. Only the fields the user changed are held by the plan. Fields not changed continue to follow the Base Plan.

**R20.** Deleting an item from the Base Plan removes it from every plan that inherits it, including plans that had changed it; the change is discarded with the item. The user is warned beforehand if the item is changed or removed in any plan.

**R21.** Adding a new Base Plan item with the same name as a deleted one creates a new item. Plans inherit it fresh, with no changes carried over.

### Plans — archiving

**R22.** Archiving retains the plan in full and removes it from the active plans list. It is fully reversible. An archived plan cannot be the active plan and does not appear in the comparison picker. Archived plans do not count toward any plan limit. The Base Plan cannot be archived.

**R23.** An archived plan continues to inherit from the Base Plan while archived. A restored plan reflects the Base Plan as it stands at the moment of restoration, not as it stood when the plan was archived.

### Plans — duplicating

**R24.** Duplicating a plan copies its changes, its removals, and its plan-only items, and gives the duplicate its own live inheritance from the Base Plan. It does not copy resulting figures or sever the inheritance link.

**R25.** A duplicate is a sibling of the source plan, not a child. Base Plan changes affect both. Changes to either the source or the duplicate do not affect the other.

**R26.** Duplicating the Base Plan produces a new plan inheriting every Base item exactly once, with no changes recorded and no plan-only copies created.

### Comparison

**R27.** When comparing two plans, the difference for each month is the second plan minus the first.

**R28.** The percentage difference is calculated against the first plan. Where the first plan's figure is zero, no percentage is shown — a dash appears instead.

**R29.** The list of items driving the difference must account for it completely. Every individual contribution added together equals the total difference exactly.

### Currency

**R30.** One currency is selected per user, and it is a label on the figures. Changing the selected currency changes the currency label and number formatting only. It never converts, recalculates or alters any amount.

**R31.** When the currency is changed after financial data has been entered, the application shows a confirmation stating plainly that amounts will not be converted.

### Dashboard periods

**R32.** The home screen carries a period selector. Income, expenses, net cash flow, Projected Balance and the outlook indicator respond to the selected period. The Current Cash Balance does not.

**R33.** Periods look forward only and always begin with the current month.

### Accuracy

**R34.** All amounts are held and calculated exactly. There is no rounding in Phase 1, because Phase 1 contains no percentages, interest rates or growth rates.

**R35.** The same information always produces the same result, regardless of when the calculation runs or which device requests it.

---

## 18. Balance foundation

### Case 18.1 — No items entered

| Setting | Value |
|---|---|
| Current Cash Balance | 45,000 as of 01-01-2026 |
| Items | None |
| Forecast start | January 2026 |
| Length | 3 months |

**Expected result**

| Month | Income | Expenses | Net | Projected balance |
|---|---|---|---|---|
| Jan 2026 | 0 | 0 | 0 | 45,000 |
| Feb 2026 | 0 | 0 | 0 | 45,000 |
| Mar 2026 | 0 | 0 | 0 | 45,000 |

*Verifies R1, R5.*

### Case 18.2 — Projected balance going negative

| Setting | Value |
|---|---|
| Current Cash Balance | 5,000 as of 01-01-2026 |
| Items | Expense "Rent" 3,000, monthly, from 01-01-2026, no end date |
| Forecast start | January 2026 |
| Length | 4 months |

**Expected result**

| Month | Expenses | Net | Projected balance |
|---|---|---|---|
| Jan 2026 | 3,000 | −3,000 | 2,000 |
| Feb 2026 | 3,000 | −3,000 | −1,000 |
| Mar 2026 | 3,000 | −3,000 | −4,000 |
| Apr 2026 | 3,000 | −3,000 | −7,000 |

Negative balances must be displayed as negative figures and not suppressed.

*Verifies R6.*

### Case 18.3 — Current Cash Balance is not changed by scheduled items

| Setting | Value |
|---|---|
| Current Cash Balance | 45,000 as of 01-01-2026 |
| Items | Income "Salary" 25,000, monthly, from 25-01-2026, no end date · Expense "Rent" 4,500, monthly, from 01-01-2026 · Expense "Utilities" 800, monthly, from 05-01-2026 |
| Today's date for this test | 26-01-2026 |

**Expected result on the home screen**

| Figure | Expected value |
|---|---|
| Current Cash Balance | **45,000**, displayed with the date 01-01-2026 |
| Projected Balance, end of January 2026 | **64,700** |

The salary date of 25 January has passed, and the rent and utilities dates have passed. **None of them has altered the Current Cash Balance.** The two figures must be separate and separately labelled on screen.

*Verifies R1, R3. This is the central behaviour agreed in this revision.*

### Case 18.4 — Updating the Current Cash Balance re-anchors the forecast

Continuing from case 18.3. The user checks their bank and updates their Current Cash Balance to **150,000 as of 01-06-2026**.

**Expected result:** the forecast is rebuilt from June 2026.

| Month | Net | Projected balance |
|---|---|---|
| Jun 2026 | 19,700 | 169,700 |
| Jul 2026 | 19,700 | 189,400 |
| Aug 2026 | 19,700 | 209,100 |
| Sep 2026 | 19,700 | 228,800 |
| Oct 2026 | 19,700 | 248,500 |
| Nov 2026 | 19,700 | 268,200 |
| Dec 2026 | 19,700 | **287,900** |

The Current Cash Balance reads 150,000 as of 01-06-2026. No month before June 2026 appears in the forecast.

*Verifies R1, R2, R11.*

### Case 18.5 — Prompt to confirm a stale balance

| Setting | Value |
|---|---|
| Current Cash Balance | 45,000 as of 01-01-2026 |
| Today's date for this test | 01-06-2026 |
| Items | The Base Plan items of section 25 |

**Expected result**

- The home screen prompts the user to confirm or update their Current Cash Balance.
- The Current Cash Balance still reads **45,000**, displayed with the date 01-01-2026. The prompt does not change it, and neither does dismissing the prompt.
- The forecast remains anchored to January 2026. Projected balance at the end of June 2026 is **163,200**.

*Verifies R1, R2.*

---

## 19. One-time items

### Case 19.1 — One-time income inside the forecast

| Setting | Value |
|---|---|
| Current Cash Balance | 10,000 as of 01-01-2026 |
| Items | Income "Bonus" 15,000, one-time, 20-03-2026 |
| Forecast start | January 2026 |
| Length | 4 months |

**Expected result**

| Month | Income | Projected balance |
|---|---|---|
| Jan 2026 | 0 | 10,000 |
| Feb 2026 | 0 | 10,000 |
| Mar 2026 | 15,000 | 25,000 |
| Apr 2026 | 0 | 25,000 |

*Verifies R7.*

### Case 19.2 — One-time item dated before the forecast starts

| Setting | Value |
|---|---|
| Current Cash Balance | 10,000 as of 01-01-2026 |
| Items | Expense "Car repair" 4,000, one-time, 15-12-2025 |
| Forecast start | January 2026 |
| Length | 3 months |

**Expected result:** the item appears in no month. All three projected balances are 10,000.

*Verifies R11. The December expense already happened and is reflected in the confirmed balance.*

### Case 19.3 — One-time item dated after the forecast period

| Setting | Value |
|---|---|
| Current Cash Balance | 10,000 as of 01-01-2026 |
| Items | Income "Bonus" 20,000, one-time, 15-03-2027 |
| Forecast start | January 2026 |

**Expected result at 12 months:** the item does not appear. December 2026 projected balance is 10,000.

**Expected result at 36 months:** the item appears in March 2027. From March 2027 onward the projected balance is 30,000.

*Verifies R7.*

---

## 20. Monthly repeating items

### Case 20.1 — Monthly income, no end date

| Setting | Value |
|---|---|
| Current Cash Balance | 45,000 as of 01-01-2026 |
| Items | Income "Salary" 25,000, monthly, from 25-01-2026, no end date |
| Forecast start | January 2026 |
| Length | 3 months |

**Expected result**

| Month | Occurs on | Income | Projected balance |
|---|---|---|---|
| Jan 2026 | 25-01-2026 | 25,000 | 70,000 |
| Feb 2026 | 25-02-2026 | 25,000 | 95,000 |
| Mar 2026 | 25-03-2026 | 25,000 | 120,000 |

*Verifies R8, R10.*

### Case 20.2 — Monthly item starting later than the forecast

| Setting | Value |
|---|---|
| Current Cash Balance | 10,000 as of 01-01-2026 |
| Items | Expense "Insurance" 1,000, monthly, from 01-03-2026, no end date |
| Forecast start | January 2026 |
| Length | 4 months |

**Expected result**

| Month | Expenses | Projected balance |
|---|---|---|
| Jan 2026 | 0 | 10,000 |
| Feb 2026 | 0 | 10,000 |
| Mar 2026 | 1,000 | 9,000 |
| Apr 2026 | 1,000 | 8,000 |

*Verifies R8.*

### Case 20.3 — Monthly item that started before the app was used

| Setting | Value |
|---|---|
| Current Cash Balance | 60,000 as of 01-01-2026 |
| Items | Income "Salary" 20,000, monthly, from 25-06-2024, no end date |
| Forecast start | January 2026 |
| Length | 3 months |

**Expected result**

| Month | Occurs on | Income | Projected balance |
|---|---|---|---|
| Jan 2026 | 25-01-2026 | 20,000 | 80,000 |
| Feb 2026 | 25-02-2026 | 20,000 | 100,000 |
| Mar 2026 | 25-03-2026 | 20,000 | 120,000 |

The salary payments from June 2024 to December 2025 are **not** added. They are already part of the confirmed balance of 60,000.

*Verifies R11. The alternative behaviour would double-count the past.*

---

## 21. Start and end dates

### Case 21.1 — End date falling on an occurrence date

| Setting | Value |
|---|---|
| Current Cash Balance | 10,000 as of 01-01-2026 |
| Items | Expense "Car loan" 2,000, monthly, from 10-01-2026, ending 10-03-2026 |
| Forecast start | January 2026 |
| Length | 4 months |

**Expected result**

| Month | Occurs on | Expenses | Projected balance |
|---|---|---|---|
| Jan 2026 | 10-01-2026 | 2,000 | 8,000 |
| Feb 2026 | 10-02-2026 | 2,000 | 6,000 |
| Mar 2026 | 10-03-2026 | 2,000 | 4,000 |
| Apr 2026 | — | 0 | 4,000 |

Three payments. March **is** included, because the end date is inclusive.

*Verifies R9.*

### Case 21.2 — End date one day before an occurrence

Identical to case 21.1 but ending **09-03-2026**.

**Expected result**

| Month | Expenses | Projected balance |
|---|---|---|
| Jan 2026 | 2,000 | 8,000 |
| Feb 2026 | 2,000 | 6,000 |
| Mar 2026 | 0 | 6,000 |
| Apr 2026 | 0 | 6,000 |

Two payments only.

*Verifies R9.*

### Case 21.3 — Start and end date on the same day

| Setting | Value |
|---|---|
| Current Cash Balance | 10,000 as of 01-01-2026 |
| Items | Expense "Fee" 500, monthly, from 10-01-2026, ending 10-01-2026 |
| Forecast start | January 2026 |
| Length | 3 months |

**Expected result:** exactly one payment, in January 2026. Projected balances 9,500 / 9,500 / 9,500.

*Verifies R9.*

---

## 22. Month-end behaviour

These cases cover the most common source of error in forecasting software. **February 2026 has 28 days.**

### Case 22.1 — Monthly on the 31st — the critical case

| Setting | Value |
|---|---|
| Current Cash Balance | 20,000 as of 01-01-2026 |
| Items | Expense "Rent" 3,000, monthly, from 31-01-2026, no end date |
| Forecast start | January 2026 |
| Length | 5 months |

**Expected result**

| Month | Must occur on | Expenses | Projected balance |
|---|---|---|---|
| Jan 2026 | **31**-01-2026 | 3,000 | 17,000 |
| Feb 2026 | **28**-02-2026 | 3,000 | 14,000 |
| Mar 2026 | **31**-03-2026 | 3,000 | 11,000 |
| Apr 2026 | **30**-04-2026 | 3,000 | 8,000 |
| May 2026 | **31**-05-2026 | 3,000 | 5,000 |

**The March date is the point of this case.** It must be the 31st. Software that carries the February adjustment forward would place it on 28 March and then remain wrong for every subsequent month.

*Verifies R12, R13.*

### Case 22.2 — Monthly on the 30th

As case 22.1, starting **30-01-2026**.

**Expected dates:** 30 Jan · **28** Feb · 30 Mar · 30 Apr · 30 May

*Verifies R12, R13.*

### Case 22.3 — Monthly on the 29th

As case 22.1, starting **29-01-2026**.

**Expected dates:** 29 Jan · **28** Feb · 29 Mar · 29 Apr · 29 May

*Verifies R12, R13.*

### Case 22.4 — Quarterly crossing a short month

| Setting | Value |
|---|---|
| Items | Expense "School fees" 9,000, quarterly, from 31-08-2026, no end date |
| Forecast start | August 2026 |
| Length | 12 months |

**Expected dates:** 31-08-2026 · 30-11-2026 · **28**-02-2027 · 31-05-2027

Four occurrences, one each in August 2026, November 2026, February 2027 and May 2027.

*Verifies R12, R13.*

---

## 23. Leap years

**2028 and 2032 are leap years. 2026, 2027, 2029, 2030 and 2031 are not.**

### Case 23.1 — Monthly on the 31st through a leap February

| Setting | Value |
|---|---|
| Items | Expense "Rent" 3,000, monthly, from 31-01-2028, no end date |
| Forecast start | January 2028 |
| Length | 4 months |

**Expected dates:** 31-01-2028 · **29**-02-2028 · 31-03-2028 · 30-04-2028

February falls on the 29th because 2028 is a leap year. Compare with case 22.1, where the same start day produced the 28th.

*Verifies R12, R14.*

### Case 23.2 — Yearly item dated 29 February

| Setting | Value |
|---|---|
| Current Cash Balance | 100,000 as of 01-02-2028 |
| Items | Expense "Annual premium" 5,000, yearly, from 29-02-2028, no end date |
| Forecast start | February 2028 |
| Length | 60 months |

**Expected occurrences**

| Occurrence | Must occur on | Reason |
|---|---|---|
| 1 | **29**-02-2028 | 2028 is a leap year |
| 2 | **28**-02-2029 | not a leap year |
| 3 | **28**-02-2030 | not a leap year |
| 4 | **28**-02-2031 | not a leap year |
| 5 | **29**-02-2032 | 2032 is a leap year |

Five payments totalling 25,000. Projected balance at the end of the period: **75,000**.

The fifth occurrence returning to the 29th is the important part — the item is anchored to the 29th permanently and adjusts only in years that have no 29th.

*Verifies R12, R13, R14.*

### Case 23.3 — Monthly item starting 29 February

| Setting | Value |
|---|---|
| Items | Expense "Subscription" 100, monthly, from 29-02-2028, no end date |
| Forecast start | February 2028 |
| Length | 13 months |

**Expected dates:** 29 Feb 2028 · 29 Mar · 29 Apr · 29 May · 29 Jun · 29 Jul · 29 Aug · 29 Sep · 29 Oct · 29 Nov · 29 Dec · 29 Jan 2029 · **28** Feb 2029

Thirteen occurrences. Only the last is adjusted.

*Verifies R12, R13, R14.*

---

## 24. Other frequencies

**1 January 2026 is a Thursday.** These cases use that anchor.

### Case 24.1 — Weekly, including months with five occurrences

| Setting | Value |
|---|---|
| Current Cash Balance | 10,000 as of 01-01-2026 |
| Items | Expense "Weekly groceries" 200, weekly, from 01-01-2026, no end date |
| Forecast start | January 2026 |
| Length | 4 months |

**Expected result**

| Month | Dates | Count | Expenses | Projected balance |
|---|---|---|---|---|
| Jan 2026 | 1, 8, 15, 22, 29 | **5** | 1,000 | 9,000 |
| Feb 2026 | 5, 12, 19, 26 | 4 | 800 | 8,200 |
| Mar 2026 | 5, 12, 19, 26 | 4 | 800 | 7,400 |
| Apr 2026 | 2, 9, 16, 23, 30 | **5** | 1,000 | 6,400 |

January and April must show 1,000, not an averaged figure.

*Verifies R15.*

### Case 24.2 — Fortnightly

| Setting | Value |
|---|---|
| Items | Income "Fortnightly pay" 5,000, every two weeks, from 01-01-2026, no end date |
| Forecast start | January 2026 |
| Length | 4 months |

**Expected result**

| Month | Dates | Count | Income |
|---|---|---|---|
| Jan 2026 | 1, 15, 29 | **3** | 15,000 |
| Feb 2026 | 12, 26 | 2 | 10,000 |
| Mar 2026 | 12, 26 | 2 | 10,000 |
| Apr 2026 | 9, 23 | 2 | 10,000 |

*Verifies R15.*

### Case 24.3 — Quarterly, half-yearly and yearly

| Setting | Value |
|---|---|
| Items | Three expenses of 1,500 each, all from 15-02-2026: one quarterly, one half-yearly, one yearly |
| Forecast start | January 2026 |
| Length | 12 months |

**Expected occurrences**

| Item | Dates | Count |
|---|---|---|
| Quarterly | 15 Feb · 15 May · 15 Aug · 15 Nov | 4 |
| Half-yearly | 15 Feb · 15 Aug | 2 |
| Yearly | 15 Feb | 1 |

*Verifies R8.*

---

## 25. Plans

Every case in this section uses the same Base Plan, defined once below.

### The shared Base Plan

| Setting | Value |
|---|---|
| Current Cash Balance | 45,000 as of 01-01-2026 |
| Income "Salary" | 25,000, monthly, from 25-01-2026, no end date |
| Expense "Rent" | 4,500, monthly, from 01-01-2026, no end date |
| Expense "Utilities" | 800, monthly, from 05-01-2026, no end date |
| Forecast start | January 2026 |
| Length | 12 months |

Monthly net position: 25,000 − 4,500 − 800 = **19,700**

### Case 25.1 — Base Plan result

| Month | Income | Expenses | Net | Projected balance |
|---|---|---|---|---|
| Jan 2026 | 25,000 | 5,300 | 19,700 | 64,700 |
| Feb 2026 | 25,000 | 5,300 | 19,700 | 84,400 |
| Mar 2026 | 25,000 | 5,300 | 19,700 | 104,100 |
| Apr 2026 | 25,000 | 5,300 | 19,700 | 123,800 |
| May 2026 | 25,000 | 5,300 | 19,700 | 143,500 |
| Jun 2026 | 25,000 | 5,300 | 19,700 | 163,200 |
| Jul 2026 | 25,000 | 5,300 | 19,700 | 182,900 |
| Aug 2026 | 25,000 | 5,300 | 19,700 | 202,600 |
| Sep 2026 | 25,000 | 5,300 | 19,700 | 222,300 |
| Oct 2026 | 25,000 | 5,300 | 19,700 | 242,000 |
| Nov 2026 | 25,000 | 5,300 | 19,700 | 261,700 |
| Dec 2026 | 25,000 | 5,300 | 19,700 | **281,400** |

### Case 25.2 — A new plan with nothing changed

Create a plan named "Test Plan" from the Base Plan and change nothing.

**Expected result:** identical to case 25.1 in every month. December 2026 projected balance **281,400**.

*Verifies R16.*

### Case 25.3 — Plan with an item added

Plan "Buy House" — Base Plan plus: Expense "Mortgage" 6,500, monthly, from 01-06-2026, no end date.

**Expected result:** identical to Base for January to May. From June the monthly net becomes 13,200.

| Month | Net | Projected balance |
|---|---|---|
| May 2026 | 19,700 | 143,500 |
| Jun 2026 | 13,200 | 156,700 |
| Dec 2026 | 13,200 | **235,900** |

Difference against Base in December: **−45,500**, being seven mortgage payments of 6,500.

*Verifies R16.*

### Case 25.4 — Plan with an item removed

Plan "No Rent" — Base Plan with "Rent" **removed**.

**Expected result:** rent is absent from every month of this plan, including January. Monthly net becomes 24,200.

| Month | Net | Projected balance |
|---|---|---|
| Jan 2026 | 24,200 | 69,200 |
| Dec 2026 | 24,200 | **335,400** |

Difference against Base in December: **+54,000**, being twelve rent payments.

*Verifies R18.*

### Case 25.5 — Plan with an item changed to end early

Plan "Rent Ends" — Base Plan with "Rent" **changed** to end 31-05-2026.

**Expected result**

| Month | Net | Projected balance |
|---|---|---|
| Jan 2026 | 19,700 | 64,700 |
| May 2026 | 19,700 | 143,500 |
| Jun 2026 | 24,200 | 167,700 |
| Dec 2026 | 24,200 | **312,900** |

Difference against Base in December: **+31,500**, being seven rent payments.

**Compare with case 25.4.** Removing an item and changing it to end early produce different results, and both are correct. This pair confirms the distinction in rule R18.

*Verifies R18.*

### Case 25.6 — A realistic combined plan

Plan "Buy House" — Base Plan with two changes:

- Expense "Mortgage" 6,500, monthly, from 01-06-2026 — **added**
- Expense "Rent" — **changed** to end 31-05-2026

**Expected result**

| Month | Net | Projected balance |
|---|---|---|
| Jan 2026 | 19,700 | 64,700 |
| Feb 2026 | 19,700 | 84,400 |
| Mar 2026 | 19,700 | 104,100 |
| Apr 2026 | 19,700 | 123,800 |
| May 2026 | 19,700 | 143,500 |
| Jun 2026 | 17,700 | 161,200 |
| Jul 2026 | 17,700 | 178,900 |
| Aug 2026 | 17,700 | 196,600 |
| Sep 2026 | 17,700 | 214,300 |
| Oct 2026 | 17,700 | 232,000 |
| Nov 2026 | 17,700 | 249,700 |
| Dec 2026 | 17,700 | **267,400** |

From June the monthly net is 25,000 − 800 − 6,500 = 17,700.

### Case 25.7 — A Base Plan change flows into every plan

From case 25.6, change the salary in the **Base Plan** from 25,000 to 28,000.

**Expected result, with no action taken inside the plan**

| Plan | December 2026 projected balance |
|---|---|
| Base Plan | **317,400** |
| Buy House | **303,400** |

*Verifies R16. A plan that quietly kept the old salary would produce a comparison the user cannot trust.*

### Case 25.8 — Plan changes never affect the Base Plan

From case 25.6, with every change made inside "Buy House":

**Expected result:** the Base Plan is unchanged. December 2026 projected balance remains exactly **281,400**, its rent still has no end date, and it contains no mortgage.

*Verifies R17.*

### Case 25.9 — Plan with a different current cash balance

Plan "Windfall" — Base Plan with the Current Cash Balance set to 345,000 instead of 45,000, and no other change.

**Expected result:** every monthly projected balance is exactly 300,000 higher than Base. December 2026: **581,400**. The Base Plan's Current Cash Balance remains 45,000.

*Verifies R1, R17.*

### Case 25.10 — Base item changed, plan had inherited it

Plan "Test Plan" (case 25.2, December 281,400). Change Base "Utilities" from 800 to 1,000.

**Expected result:** both Base and Test Plan show December 2026 projected balance **279,000**.

*Verifies R16, R19.*

### Case 25.11 — Base item changed in a field the plan did not override

Plan "Rent Ends" (case 25.5) has rent changed to end 31-05-2026 and nothing else. December was 312,900. Change the Base Plan rent amount from 4,500 to 5,000.

**Expected result**

| Plan | Jan–May monthly net | Jun–Dec monthly net | December 2026 projected balance |
|---|---|---|---|
| Base Plan | 19,200 | 19,200 | **275,400** |
| Rent Ends | 19,200 | 24,200 | **310,400** |

"Rent Ends" must use the **new** rent amount of 5,000 for January to May while keeping its own May end date. A December figure of 312,900 would mean the plan is still using the old amount, and would be a defect.

*Verifies R19. This is the most important case in this section.*

### Case 25.12 — Base item deleted, plan had inherited it

Plan "Test Plan" (no changes). Delete "Utilities" from the Base Plan.

**Expected result:** both plans show December 2026 projected balance **291,000**. Utilities appears in neither.

*Verifies R20.*

### Case 25.13 — Base item deleted, plan had changed it

Plan "Rent Ends" (rent changed to end 31 May). Delete "Rent" from the Base Plan.

**Expected result**

- Before deletion, a warning states that rent is changed in one of the user's plans.
- After deletion, rent appears in neither plan, and the end-date change is discarded.
- Base Plan December 2026: **335,400**
- "Rent Ends" December 2026: **335,400**

*Verifies R20.*

### Case 25.14 — Base item deleted, plan had removed it

Plan "No Rent" (case 25.4, December 335,400). Delete "Rent" from the Base Plan.

**Expected result:** "No Rent" is unchanged at **335,400**. Base Plan becomes **335,400**. No warning is required for a plan that had already removed the item.

*Verifies R20.*

### Case 25.15 — Duplicate preserves inheritance and changes

From the Base Plan and "Buy House" of case 25.6 (December 267,400).

| Step | Action | Expected result |
|---|---|---|
| 1 | Duplicate "Buy House" as "Buy House (copy)" | Every month identical to "Buy House". December 2026: **267,400** |
| 2 | Inspect the copy's items | Salary and utilities shown as inherited from Base · Rent shown as changed, ending 31-05-2026 · Mortgage shown as existing only in this plan |
| 3 | Change Base Plan salary from 25,000 to 28,000 | Base **317,400** · Buy House **303,400** · Buy House (copy) **303,400** |
| 4 | In the copy only, change the mortgage from 6,500 to 7,000 | Buy House (copy) **299,900** · Buy House unchanged at **303,400** · Base unchanged at **317,400** |

Step 3 proves the inheritance link survives duplication. Step 4 proves the two plans are independent of each other.

*Verifies R24, R25.*

### Case 25.16 — Duplicating the Base Plan

| Step | Action | Expected result |
|---|---|---|
| 1 | Duplicate the Base Plan as "New Plan" | December 2026 projected balance **281,400**, identical to Base in every month |
| 2 | Inspect the items | Salary, rent and utilities each appear **exactly once**, all shown as inherited from Base. No item is shown as existing only in this plan |
| 3 | Change Base Plan utilities from 800 to 1,000 | Both Base and "New Plan" show December 2026 projected balance **279,000** |

Step 2 is the point of this case. Producing six items instead of three would be a defect.

*Verifies R26.*

### Case 25.17 — Archive and restore, with a Base change in between

From the Base Plan and "Buy House" of case 25.6.

| Step | Action | Expected result |
|---|---|---|
| 1 | Archive "Buy House" | Absent from active plans; present in Archived; unavailable in the comparison picker. If it was the active plan, the app switches to Base |
| 2 | Change Base Plan salary from 25,000 to 28,000 | Base Plan December 2026: **317,400** |
| 3 | Restore "Buy House" | Present in active plans, with its mortgage and its rent end-date change intact |
| 4 | View "Buy House" forecast | December 2026: **303,400**, reflecting the new salary |

*Verifies R22, R23.*

---

## 26. Comparison

### Case 26.1 — Comparing Base Plan against Buy House

Plan A: Base Plan (case 25.1). Plan B: Buy House (case 25.6). Period: 12 months.

**Expected comparison**

| Month | Plan A | Plan B | Difference |
|---|---|---|---|
| Jan 2026 | 64,700 | 64,700 | 0 |
| May 2026 | 143,500 | 143,500 | 0 |
| Jun 2026 | 163,200 | 161,200 | −2,000 |
| Jul 2026 | 182,900 | 178,900 | −4,000 |
| Dec 2026 | 281,400 | 267,400 | **−14,000** |

**Expected headline figures**

- Difference at the end of the period: **−14,000**
- Percentage difference: **−4.98%**

*Verifies R27, R28.*

### Case 26.2 — What is driving the difference

For the same comparison, the application must list:

| Item | Change | Contribution |
|---|---|---|
| Mortgage | Added in Buy House | **−45,500** |
| Rent | Ends earlier in Buy House | **+31,500** |
| Salary | Unchanged | not listed |
| Utilities | Unchanged | not listed |

**The contributions must add up exactly:** −45,500 + 31,500 = **−14,000**, matching the total difference.

Unchanged items are not listed.

*Verifies R29. This check is applied automatically to every comparison the software produces, not only to this case.*

### Case 26.3 — Percentage where the baseline is zero

Plan A has a projected balance of 0 in a given month. Plan B has 5,000.

**Expected result:** the difference shows as +5,000. The percentage shows as a dash. It must not show 0%, and it must not show an error.

*Verifies R28.*

---

## 27. Forecast horizons and dashboard periods

### Case 27.1 — The four forecast horizons

Using the Base Plan of section 25:

| Horizon selected | Months shown | Final month |
|---|---|---|
| 1 year | 12 | Dec 2026 |
| 3 years | 36 | Dec 2028 |
| 5 years | 60 | Dec 2030 |
| 10 years | 120 | Dec 2035 |

**Expected projected balance at 10 years:** 45,000 + (120 × 19,700) = **2,409,000**

### Case 27.2 — Changing the horizon does not change the figures

Any month appearing in more than one horizon shows identical figures in each. December 2026 shows 281,400 whether the 1, 3, 5 or 10 year view is selected.

*Verifies R35.*

### Case 27.3 — Dashboard selected-period totals

Using the Base Plan of section 25, with the current month being January 2026:

| Period selected | Income | Expenses | Net | Projected Balance at period end |
|---|---|---|---|---|
| This month | 25,000 | 5,300 | 19,700 | **64,700** |
| Next 3 months | 75,000 | 15,900 | 59,100 | **104,100** |
| Next 6 months | 150,000 | 31,800 | 118,200 | **163,200** |
| Next 12 months | 300,000 | 63,600 | 236,400 | **281,400** |

In every case the Current Cash Balance continues to read **45,000 as of 01-01-2026** and does not respond to the period selection.

Each Projected Balance must match the same month's figure in the forecast table exactly.

*Verifies R32, R33, R1.*

---

## 28. Currency

### Case 28.1 — Changing currency does not convert amounts

| Step | Action | Expected result |
|---|---|---|
| 1 | Base Plan with Saudi Riyal selected | Salary reads 25,000 SAR. December 2026 projected balance reads 281,400 SAR |
| 2 | Change currency to US Dollars | A confirmation is shown, stating that amounts will not be converted |
| 3 | Confirm | Salary reads 25,000 USD. December 2026 projected balance reads 281,400 USD |
| 4 | Compare every figure against step 1 | Every numeric value is identical. Only the currency label has changed |

*Verifies R30, R31.*

---

## 29. Integrity checks

These are not single cases. They are applied automatically to every projection the software produces, including every case above and thousands of randomly generated combinations.

### Check 29.1 — Everything balances

For any projection, the final projected balance must equal the Current Cash Balance, plus every income occurrence, minus every expense occurrence, across the whole period.

Verified against case 25.6:
45,000 + 300,000 (salary) − 22,500 (rent, five months) − 9,600 (utilities) − 45,500 (mortgage, seven months) = **267,400** ✔ matching the December figure.

*This is the direct check against your RFP requirement that forecast calculations reconcile to the underlying transaction model.*

### Check 29.2 — Results are repeatable

The same information produces an identical result every time, regardless of when the calculation runs or which device requests it.

### Check 29.3 — Plans stay separate

No change made inside any plan alters the result of any other plan, other than through the intended inheritance from the Base Plan described in R16.

### Check 29.4 — Comparisons are fully explained

For every comparison, the listed contributions add up exactly to the total difference.

---

## 30. Template for your own test cases

Please add any cases you wish. A case does not need to be complicated to be valuable — the most useful are usually drawn from real financial situations.

```
Case reference:          C-01
What it checks:

Current Cash Balance:            as of
Items:
  1. [Income/Expense] "name" — amount — frequency — from date — end date (or none)
  2.
  3.

Forecast start:
Length:

Expected result:
  Month | Income | Expenses | Net | Projected balance
  ------|--------|----------|-----|------------------
        |        |          |     |
        |        |          |     |

Notes:
```

A spreadsheet works equally well — we will convert it into this format and into our automated tests.

---

## 31. How these cases are used

**During development.** Every case becomes an automated test before the corresponding feature is built. A feature is complete when its cases pass.

**Throughout the project.** The full set runs automatically on every change. A change that breaks any agreed case cannot be released, which means a rule agreed at M1 cannot be quietly broken in month four.

**At acceptance.** We provide the test execution report and traceability table described in section 9.2. Your acceptance testing confirms these results rather than discovering them.

**After delivery.** The suite is part of the source code you own. It remains a permanent record of the agreed rules and protects the product's accuracy through any future change, by anyone.

---

## 32. Milestone 1 closure

On signature of this document, Milestone 1 is complete and M2 — Design — begins.

The three decisions in section 11 marked "needed before M2" should be confirmed alongside signature, as design cannot begin without them.

---

## 33. Agreement

By signing below, both parties agree that:

- Part 1 is the agreed specification for Phase 1, including the scope boundaries in sections 9 and 10.
- The financial rules in section 17 and the test cases in sections 18 to 29 are the objective reference for development, automated testing and final acceptance.
- Any behaviour of the delivered application that disagrees with an agreed rule or an agreed test case is a defect, correctable within the agreed Phase 1 scope, as stated in section 14.

**Agreed on behalf of [Client Name]**

Name: ................................................

Position: ................................................

Signature: ................................................

Date: ................................................

**Agreed on behalf of [Company Name]**

Name: ................................................

Position: ................................................

Signature: ................................................

Date: ................................................
