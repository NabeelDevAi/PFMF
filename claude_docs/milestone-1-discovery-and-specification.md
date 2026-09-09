# Milestone 1 — Discovery & Specification

**Personal Financial Management & Forecasting Application — Phase 1**

Prepared for: [Client Name]
Prepared by: [Company Name]
Date: [Date]
Version: 1.0 — for review and confirmation

---

## 1. What this document is for

This document sets out exactly what we understood from your RFP, exactly what we plan to build in Phase 1, and exactly what we are not building.

It has three jobs:

1. **Confirm we understood you correctly.** If anything below does not match what you had in mind, this is the moment to tell us — before design and development begin, when changes cost nothing.
2. **Agree the boundary of Phase 1.** A fixed price needs a fixed scope. Section 9 lists what is included and section 10 lists what is not, so there is no ambiguity later.

Once you have reviewed this and we have worked through the questions together, this document becomes the agreed specification for Phase 1. Everything we build is measured against it.

You do not need a technical background to read this. There is nothing here about code or databases. If you would like this document in Arabic, we are happy to provide it.

---

## 2. What we are building, in one paragraph

A mobile app for iPhone and Android, in Arabic and English, that lets a person enter their income and expenses, see a projection of their cash balance for up to ten years ahead, create alternative plans such as "what if I buy a house," and compare those plans side by side to see which leaves them better off.

The product philosophy in your RFP was **Track → Understand → Forecast → Simulate → Decide**. Phase 1 builds the reliable foundation: entering your financial picture, projecting it forward accurately, and comparing alternatives. Phase 2 adds the intelligence layer on top.

---

## 3. How the app works

This section explains the ideas behind the product in everyday language. These concepts drive every screen, so it is worth reading carefully.

### 3.1 Your financial picture

The app holds three things about you:

**Your starting balance.** How much cash you have right now. You enter this when you first set up the app, and you can change it any time.

**Your income.** Salary, bonuses, rental income, anything that comes in.

**Your expenses.** Rent, utilities, subscriptions, loan payments, school fees, anything that goes out.

Everything the app shows you is built from these three things.

### 3.2 One-time and repeating items

Every income or expense is either **one-time** or **repeating**.

A one-time item happens once on a specific date — a bonus in December, a car repair in March.

A repeating item happens on a schedule. You choose from: weekly, every two weeks, monthly, quarterly, every six months, or yearly. You set a start date, and optionally an end date if it stops at some point — a car loan that finishes in three years, for example.

One useful detail: if you set something to repeat monthly on the 31st, the app places it on the last day of any shorter month. So a payment on the 31st of January falls on the 28th of February, then back to the 31st of March. The app tells you this on screen when you pick such a date, so nothing is surprising.

### 3.3 Plans — the most important idea in the app

This is what makes the product a decision tool rather than a budget tracker, so it is worth explaining properly.

**Your Base Plan is your real life as it stands today.** Your actual salary, your actual rent, your actual commitments. This is where you start, and it is where you spend most of your time.

**A new plan is a version of your life where something is different.** You might create one called "Buy House." When you create it, it begins as your real life — everything from your Base Plan is already in it. You then change only what would actually be different: add a mortgage payment, add a down payment as a one-time expense, remove your current rent because you would no longer be paying it.

Everything you did not touch stays connected to your Base Plan. This matters more than it might sound. **If your salary increases, you update it once in your Base Plan, and every alternative plan you have created updates automatically.** You never maintain the same information in five places, and your plans never quietly go out of date.

The app always shows you which plan you are currently looking at, and marks any item that has been changed or removed within a plan, so you always know where you are and what you have altered.

Your Base Plan is never changed by anything you do inside another plan. That protection is built into how the system works, not left to careful use.

### 3.4 The forecast

Once your income and expenses are in, the app projects forward month by month. For each month it shows how much comes in, how much goes out, the difference between them, and what your cash balance will be at the end of that month.

You can look ahead one year, three years, five years or ten years.

You can also tap any month to see exactly which items produced that number. We consider this important: a forecast you can inspect is a forecast you can trust, and if a figure ever looks wrong you can see the reason immediately rather than wondering.

### 3.5 Comparing plans

You pick two plans and a time horizon, and the app shows you:

- The difference in your cash balance at the end of the period, in riyals and as a percentage
- A chart with both plans drawn together
- A month-by-month table showing both plans and the difference
- **A plain list of what is causing the difference** — for example, that the mortgage costs you SAR 32,400 more over five years, while no longer paying rent saves you SAR 21,600

That last item is the part we think you will use most. A chart tells you *that* two plans differ. This tells you *why*, item by item, and the individual figures add up exactly to the total difference.

---

## 4. Walking through it as a user would

### Setting up, the first time

Ahmed downloads the app and chooses Arabic. He creates an account, confirms his currency is Saudi Riyal, and enters his current cash balance of SAR 45,000. The app asks him to add his income, so he enters his salary of SAR 25,000, monthly, starting from the 25th of this month. He lands on the home screen and already sees a projection.

### Building the picture

Over the next few minutes he adds his rent, utilities, school fees, car loan (with an end date in two years, because that is when it finishes), and his phone and streaming subscriptions. Each takes a few seconds. The home screen updates as he goes.

### Looking ahead

He opens the forecast and selects five years. He sees his balance climbing steadily, with a visible step up in two years when the car loan ends. He taps that month out of curiosity and sees exactly which items are in it, confirming the loan has dropped off.

### Trying a decision

Ahmed is considering buying a house. He creates a plan called "Buy House." All his existing information is already there. He adds a down payment of SAR 300,000 as a one-time expense next June, adds a monthly mortgage payment of SAR 6,500 starting the same month, and removes his rent from this plan — the app confirms that his rent remains untouched in his Base Plan.

### Deciding

He compares "Buy House" against his Base Plan over ten years. He sees where the down payment takes his balance down sharply, how long it takes to recover, and where the two lines cross. The list underneath tells him the mortgage costs him SAR 780,000 over ten years while removing rent saves SAR 504,000. He now has a number to think about instead of a feeling.

### Life changes

Six months later Ahmed gets a raise. He updates his salary once, in his Base Plan. His "Buy House" plan and his two other plans all reflect the new salary immediately, because they were never separate copies.

---

## 5. What is in the app

Around **34 screens and panels**, grouped into six areas:

**Getting started** — language selection, sign up, sign in, password reset, and a short setup asking for your currency, starting balance and first income.

**Home** — your current balance, this month's income, expenses and net position, your projected balance, a simple indicator of whether your position is improving or worsening, and a chart of the year ahead. Also where you switch between plans.

**Income & expenses** — the full list, grouped by income and expense, with search and filtering. Adding or editing an item covers name, amount, category, schedule and optional notes.

**Forecast** — the projection as a chart and as a month-by-month table, with one, three, five and ten year views, three chart views (balance, income against expenses, and net cash flow), and the ability to open any month and see what is inside it.

**Plans** — create, rename, duplicate, archive and delete plans, see what makes each plan different from your Base Plan, and compare any two plans.

**Settings** — profile, currency, language, starting balance, password, data export, data reset, account deletion.

---

## 6. Arabic and English

Both languages are in the app from the first release, in a single app rather than two separate versions.

- Arabic reads right to left throughout. Not only the text — the whole layout, including menus, forms and navigation.
- Language is chosen before you even create an account, so nothing is ever shown in the wrong language.
- Language can be changed at any time in settings, and takes effect immediately.
- Dates, numbers and currency are formatted correctly for the chosen language.
- Charts and tables work properly in both directions.
- The app is built so that a third language can be added later by supplying translations, without redevelopment.

---

## 7. How we make sure the numbers are right

Your RFP asks how we ensure the calculation engine is accurate and testable. This is the part of the project we take most seriously, so here is our approach in plain terms.

**The calculation is built as a separate, self-contained piece of software.** It is not mixed into the app screens or the database. It takes your financial information in and produces the projection out, and it has no other job. This means it can be tested completely on its own, thoroughly, before it is connected to anything.

**It is built first.** Before any screen is built, before the app can even be logged into, the calculation engine is finished and tested. It is the part of the project that matters most, so it gets built when the team is freshest and there is the most time to get it right.

**It is tested against hundreds of specific cases**, including the awkward ones: payments on the 31st in February, yearly payments dated the 29th of February, weekly payments in months that contain five of them, items that end mid-year, items that started before you began using the app.

**We also check the whole thing balances.** Every projection is automatically verified to confirm that the final balance equals your starting balance plus every single item in between. If a projection ever failed to add up, the software would refuse to build.

**One request.** Your RFP mentions that comparison results must match your independently verified test cases. Please share those with us during discovery. We will build them directly into our automated testing, which means that by the time we hand the product over, your own test cases have already been passing on every single build for months. Acceptance then becomes a matter of confirmation rather than discovery.

**All calculations happen on the server, in one place.** Not partly in the app and partly on the server, which is a common source of figures that disagree with each other. One calculation, one answer, everywhere it appears.

---

## 8. How Phase 2 builds on this without rework

Your RFP asks how we structure Phase 1 so that Phase 2 does not require rebuilding it. Here is the answer without technical language.

The calculation engine works on a simple principle: it accepts a list of dated amounts and works out the running balance. It does not care where those amounts came from.

That means every Phase 2 feature can be added by feeding the same engine, rather than replacing it.

**Financial events** — buying a house, taking a loan, planning a trip — become shortcuts that produce ordinary income and expense items. A house purchase becomes a down payment plus a monthly mortgage plus annual insurance. The engine treats these exactly like anything else you entered by hand. Nothing about it changes.

**What-if analysis** is a plan created automatically from one of those events, forecast and compared using machinery that already exists in Phase 1.

**Best case, expected case and worst case** projections are the same engine run three times with different assumptions. We are building the place where those assumptions plug in during Phase 1, deliberately doing nothing, so that Phase 2 has somewhere to connect.

**Inflation and salary growth** adjust the amounts before the engine adds them up. This is a single, contained addition.

**The AI assistant** suggests changes and answers questions, but never calculates anything itself. It proposes; the same tested engine computes. Your RFP requires exactly this, and structuring it this way makes it a genuine guarantee rather than a promise.

**Bank tracking and multiple accounts** are additions to the existing structure, not replacements for it.

Every Phase 2 feature either feeds the engine or reads its output. Nothing reaches into the middle and changes how it works.

---

## 9. What is included in Phase 1

| Area | What you get |
|---|---|
| **Accounts** | Sign up, sign in, password reset, profile, secure sessions |
| **Setup** | Language, currency, starting balance |
| **Home** | Current balance, monthly income and expenses, net position, projected balance, outlook indicator, 12-month chart |
| **Income & expenses** | Add, edit, delete; one-time and repeating; categories; notes; start and end dates; search and filter |
| **Plans** | Create, rename, duplicate, archive, delete; changes isolated from your Base Plan; automatic inheritance of unchanged items |
| **Forecast** | Monthly projection over 1, 3, 5 and 10 years; income, expenses, net and balance; month-by-month breakdown |
| **Comparison** | Two plans side by side; chart; monthly table; differences in amount and percentage; explanation of what is driving the difference |
| **Charts** | Balance over time, income against expenses, net cash flow, plan comparison; monthly and annual summaries |
| **Languages** | Arabic and English, full right-to-left support, one app |
| **Settings** | Currency, profile, language, starting balance, plan management, data export, data reset, account deletion |
| **Platforms** | iPhone and Android |
| **Delivery** | Designs, working app, backend, automated tests, App Store and Google Play submission, source code, documentation |

---

## 10. What is not included in Phase 1

This is the most important section for both of us. Everything below is genuinely useful and most of it belongs in Phase 2 or later. None of it is in the Phase 1 price. If any item here is something you consider essential for the first release, tell us now and we will price it — that is a straightforward conversation today and a difficult one in three months.

**Bank connection.** The app does not connect to your bank. You enter your figures yourself.

**Recording actual spending.** Phase 1 is a planning tool. You describe what you earn and spend; the app projects it forward. It does not ask you to tick off each payment as it happens, and it does not compare what you planned against what actually occurred. That is a different kind of product feature and it belongs in Phase 2.

**Multiple accounts.** Phase 1 works with a single overall cash position rather than separate current, savings and investment accounts with transfers between them.

**Currency conversion.** You choose one currency and everything is shown in it. The app does not convert between currencies or hold balances in more than one.

**Offline use.** The app requires an internet connection. This is a deliberate consequence of running every calculation in one place on the server, which is what guarantees the figures always agree.

**Notifications and reminders.**

**Fingerprint or Face ID login.** The app is built so this can be added later without rework, but it is not built in Phase 1.

**Budgets and spending limits.**

**Loan schedules and amortisation tables.**

**Investments, assets, and net worth tracking.**

**Financial health scores, financial freedom planning, and automated recommendations.** These are named in your RFP as Phase 2.

**AI assistant.** Phase 2.

**What-if analysis and financial events.** Phase 2.

**Dark mode.** Not mentioned in the RFP and not currently priced. If you want it, it is best decided before design begins — adding a second visual theme across 34 screens later is considerably more expensive than accounting for it now.

**Tablet and web versions.** Phone layouts only.

---

## 14. Confirmation

Please review this document and let us know:

1. Anything in sections 3 to 6 that does not match what you had in mind
2. Anything in section 10 that you consider essential for Phase 1
4. Anything missing entirely

We will then work through it with you, produce a final version, and treat that as the agreed specification for Phase 1.

---
