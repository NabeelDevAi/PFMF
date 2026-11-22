# Flutter client audit (Horizon)

**Date:** 2026-10-16
**Repo audited:** `PFMP-Flutter` (branch at commit `ee10057`)
**Backend reference:** `https://api-finance-forecast.com/v1` (live)
**Method:** static code read only. Nothing was built, run or changed in the Flutter repo.

**Coverage:**
- **Read in full:** network layer, auth, session and token storage, router, account set-up wizard, settings (all services/controllers), profile/currency/locale, plan/transaction/forecast core, home dashboard and transactions controllers, Android and iOS platform config.
- **Skimmed:** Plans, Compare and Forecast widgets, edit-transaction form.
- **Not reviewed:** English/Arabic string parity, widget-level layout, and the 40 test files.

---

## 1. Endpoint coverage

The API index lists 33 endpoints. The client calls 29 of them, each with the correct method, path and body shape. The other 4 are unused because no screen needs them (see below).

| Area | Endpoints | Client status |
|---|---|---|
| Auth | register, login, refresh, logout | Integrated |
| Me | `GET /me`, `PATCH /me/settings`, `PUT /me/balance`, `PATCH /me/password`, `DELETE /me`, `DELETE /me/data`, `GET /me/export` | Integrated |
| Plans | list, create (sends a list of names), rename, archive, unarchive, duplicate, delete | Integrated. `GET /scenarios/{id}` is unused (the list already has every field). |
| Transactions | list (filter), create, patch, delete, dependents | Integrated |
| Overlays | create (override/exclude), patch, delete | Integrated |
| Forecast | per-plan forecast (with occurrences), compare | Integrated |
| Categories | `GET /categories` only | Integrated. Create/rename/delete are unused (no screen). |

**Out of scope by design (kept for phase 2, not findings):**

| Item | State |
|---|---|
| Set-up goals | Static by design. Step 1 collects them, but `ApiConstants.accountSetup` is `null`, so they are never sent anywhere. |
| Subscription / paywall | Parked for the next phase. `subscriptionPlans` and `subscribe` are `null`, plans are hard-coded, Subscribe is a no-op, and the paywall route is not linked from anywhere. |
| `/products` sample | Leftover template reference code, still wired in (`HomeController`, `HomeItemDetailScreen`). Not a backend endpoint. |

**Backend endpoints the client never calls:** `GET /scenarios/{id}`, `POST/PATCH/DELETE /categories` (no screen), and `GET /health`, `GET /health/db` (monitoring only). Confirmed by grep: the only uses of `ApiConstants.scenario(id)` are rename (`PATCH`) and delete (`DELETE`) in `plan_service.dart`.

---

## 2. Fix before release (High)

**Status (2026-10-17):** all six applied in `PFMP-Flutter` (uncommitted, not run or tested, per the no-run rule).
- **H1:** set-up income now sent as `income`; the test expectation was updated.
- **H2:** option 2: login sets `accountSetupDone` before the session starts; sign-up still opens the wizard.
- **H3:** `rememberAppFlow = true` (the old behaviour is now a dev override).
- **H4:** the dashboard no longer falls back to demo data or estimates. A missing plan (reloaded first), balance, forecast or this-month items is an error with Retry. Test `home_screen_test.dart` "forecast fails" was rewritten. **Still to repair:** `home_dashboard_controllers_test.dart` currency test (needs plan fakes), and possibly the "Scenario" test in `home_screen_test.dart` that sets `forecasts.failing = true`.
- **H5:** onboarding privacy note reworded (en/ar, including generated l10n files). Terms and Privacy Policy links are **deferred** (no URLs, no `url_launcher`); needed before store submission.
- **H6:** `BasePlanController.validateSelection()` runs from the splash for signed-in users (5 s cap); a deleted or archived selected plan falls back to the Base Plan. The optional 404 safety net was not added.

### H1. Salary entered at set-up is saved as an expense — FIXED
- **Where:** `lib/modules/account_setup/controllers/setup_income_controller.dart`, `static const TransactionDirection direction = TransactionDirection.expense`.
- **Effect:** the "first income" step posts the user's income to the Base Plan with `direction: "expense"`. Every forecast built on it has the wrong sign, and the "tracked items" count on the Ready screen counts it as one.
- **Question for you:** was this deliberate (for example a test toggle left in)? It looks like a bug.

### H2. Returning users are sent back through the set-up wizard — FIXED
- **Where:** `lib/app/routes/app_router.dart:63` reads `accountSetupDone`, which is only ever set locally at the end of the wizard (`setup_submit_controller.dart`). Login does not set it, and `clearSession` clears it.
- **Effect:** after logout then login, on a new device, or after a reinstall, the user is redirected to `/setup`. Re-running the wizard:
  - overwrites their real balance via `PUT /me/balance`
  - adds the income transaction a second time
  - fails plan creation with `scenario.name_taken` for existing plan names
- **Affects the app today**, not only after H3 is fixed.

### H3. `rememberAppFlow = false` — FIXED
- **Where:** `lib/core/constants/app_constants.dart:23`, used in `lib/main.dart:21`.
- **Effect:** every launch clears the tokens, the "logged in" flag, onboarding state and set-up state, so the user is signed out on every app start. This must be `true` for a release.
- **Note:** turning it on makes H2 and H6 visible in normal use.

### H4. Fake numbers can appear as real ones — FIXED
- **Where:** `lib/modules/home/controllers/home_dashboard_controller.dart` and `lib/modules/home/models/home_dashboard_model.dart`.
- **Demo data:** if the selected plan ID is `null`, the dashboard uses the bundled demo model: "Muhammad", SAR 72,400 balance, SAR 18,000 salary, rent, car loan and so on. This happens when the Base Plan load fails after login or signup. That load is best-effort and its failure is swallowed (`login_controller.dart`, `signup_controller.dart`). `withCurrency` also falls back to the demo balance when the real one is `null` (`cashBalance ?? this.cashBalance`).
- **Synthetic chart:** if the forecast request fails, the dashboard "estimates" from transactions using a made-up seasonal table (`_season`). It is drawn as a normal chart, with nothing telling the user it is an estimate.
- **Why it matters:** this is a finance app, and a network blip makes it show invented figures with no warning.

### H5. Privacy copy is false and legal links are missing — WORDING FIXED, LINKS DEFERRED
- **Where:** `app_en.arb` `onboardingPrivacyNote`: "No bank connection. You decide what to track, and it stays on your device." The data is stored on your server.
- **Terms and Privacy Policy:** `signupTerms` says "By continuing you agree to the Terms and Privacy Policy", but it is plain text with no link, and no privacy policy exists anywhere in the app.
- **Why it matters:** both stores require a privacy policy link and an accurate data-collection disclosure. A false "stays on your device" claim is a compliance and trust problem.

### H6. A stale selected plan can lock the app — FIXED
- **Where:** `lib/core/session/base_plan.dart`. The selected plan is saved to SharedPreferences and nothing re-validates it at start-up. It is only refreshed after actions taken on this device (`HomePlansController._reload`).
- **Effect:** if that plan was deleted or archived from another device, every transactions or forecast call returns 404. The dashboard shows an error, and Retry fails every time because the same ID is reused.

---

## 3. Medium

| # | Issue | Where | Effect |
|---|---|---|---|
| M1 | **DEFERRED (rare case, decided 2026-10-17).** **Currency mismatch for new accounts on a used device.** The device keeps the last currency after sign-out. `CurrencyController.change` skips the `PATCH` when the picked code equals the current state. | `currency_controller.dart`, `setup_currency_screen.dart` | The server keeps its default (`SAR`), the app shows the device currency, and the next `GET /me` flips the app to SAR. |
| M2 | **FIXED 2026-10-17 (server checked before creating; backend `POST /scenarios` verified all-or-nothing).** **Set-up is not safe to retry.** The "already sent" memory is in-process only. | `setup_income_controller.dart`, `setup_submit_controller.dart` | Killing the app mid-wizard re-adds the income. If plan creation succeeds but the response times out, the retry returns `scenario.name_taken` for every name. Backend batch atomicity was not checked. |
| M3 | **FIXED 2026-10-17 (lists reload in a `finally`).** **"Remove from this plan" on a Modified row is two calls** (delete overlay, then exclude) and is not atomic. | `home_transactions_controller.dart` `remove()` | If the second call fails, the row has already reverted to inherited, but the lists are not reloaded and an error is shown. |
| M4 | **FIXED 2026-10-17 (9 integer digits + 2 decimals on set-up amount fields; no server-side bound added).** **No input bounds on set-up amounts.** The balance and income fields allow unlimited digits. The server has no upper bound (BigInteger) and no name-length limits. | `balance_fields.dart`, backend `api/schemas` | A huge value can overflow into a 500 or garbage output. The add-transaction keypad does cap at 9 digits, and client caps on names (60/40/500) are not enforced server-side. |
| M5 | **DEFERRED 2026-10-17; lower impact than first written: the backend never reads `Accept-Language` (errors carry both `message_en`/`message_ar`), the stored `locale` is only used by the export.** **Language is not synced with the account.** `Accept-Language` is only sent once the user has chosen a language. Signup does not send a locale. The server's locale from `GET /me` is parsed but never applied. | `api_client.dart`, `locale_controller.dart`, `user_profile.dart` | Arabic-device users keep `locale: "en"` on the server. A new device never restores the saved language. |
| M6 | **CHANGED 2026-10-17 by decision: exports are kept on the device permanently (no cleanup). Export now saves individual, date-time-named files (CSV ZIP unpacked client-side with `archive`; Android `Download/Horizon`, iOS Files app via `file_saver`; share sheet only as fallback). New deps: `archive`, `file_saver` (run `flutter pub get`). Avatar disk-cache eviction on sign-out NOT done.** **Local data is not cleaned up.** The export (all financial data, unencrypted) is written to the cache directory and never deleted. The avatar disk cache also survives. | `settings_account_controller.dart` | Files remain after logout, reset and account deletion. |
| M7 | **FIXED 2026-10-17 (set-up and `/ready` removed from `publicRoutes`; `/paywall` left public, parked; `/password-updated` stays public by design).** **Flow routes are public while signed out.** `/setup/*`, `/paywall`, `/ready` and `/password-updated` are in `publicRoutes`. Comments still describe a "demo sign-up". | `app_routes.dart`, `setup_ready_screen.dart` | No data leaks (API calls return 401), but a signed-out user can open these screens. |

---

## 4. Low / hardening / cleanup

- **Release signing (DEFERRED 2026-10-17; see "Pre-launch checklist" below):** `build.gradle.kts` falls back to the **debug signing key** when `key.properties` is missing. No minify or obfuscation is enabled. The app ID is still the placeholder `com.horizon.horizon`.
- **Certificate pinning (DEFERRED 2026-10-17, decided out for phase 1; revisit before bank connections/payments):** none. Acceptable for phase 1 but worth an explicit decision for a finance app.
- **Silent parse defaults mask backend drift (FIXED 2026-10-17: `PlanTransaction.fromJson` required fields and `ForecastMonth.month` are now strict and throw `FormatException`; optional fields stay lenient; `ForecastMonth` income/expense/closing amounts still default to 0):**
  - `PlanTransaction.fromJson`: unknown `direction` becomes expense, unknown `origin` becomes own, a bad `start_date` becomes now.
  - `ForecastMonth.fromJson`: a bad month becomes 1970.
- **Arabic keyboards (DEFERRED 2026-10-17; also: the edit-transaction amount regex `^\d{0,9}\.?\d{0,2}` lets 2 extra digits through, fix with `^\d{0,9}(\.\d{0,2})?`):** amount filters use `\d`, which blocks Eastern Arabic digits.
- **Schedule wording vs start date (FIXED 2026-10-17, wording only: set-up notes now say "Every month, starting today" / "Every 3 months, starting today"; a start-date picker was not added):** new transactions always start today (`startDate: DateTime.now()`). Verify the schedule notes (for example "Every month on the 1st") do not promise a different day.
- **Dead code to remove (DEFERRED 2026-10-17; nothing broken by leaving it. Safe first step later: the `/products` sample only; `homeCreatedPlansProvider` looks unused; `homePlanEditsProvider` is still live and `homeBaseTxEditsProvider` is only reachable in the now-unreachable demo branch of `home_edit_transaction_screen.dart`):** `/products` sample, `HomeController` and `HomeItem*`, local `homeBaseTxEdits` and `homeCreatedPlans` / `homePlanEdits`. (Paywall and subscription module are intentionally kept for phase 2.)
- **Stale docs (DEFERRED 2026-10-17, no impact on the app):** the Flutter copy of `API-ENDPOINTS.md` §6 shows `name` as a string. The backend now requires a list and the client code already sends one.
- **Delete account and Reset data (DEFERRED 2026-10-17; keep confirm-only for phase 1, consider backend-enforced `current_password` on `DELETE /me` and `DELETE /me/data` in the next phase):** only a confirm dialog, no password re-entry. The server does not require it either, so this is a design decision.
- **Release metadata (DEFERRED to the developer checklist, section 7):** `PrivacyInfo.xcprivacy` (iOS) and the Play data-safety answers were not checked.

---

## 5. Verified as correct

- **Token storage:** access and refresh tokens are in Keychain/Keystore (`first_unlock_this_device`), never in SharedPreferences. `allowBackup` and `fullBackupContent` are off. A Keychain survivor from a reinstall is cleared at start-up.
- **Token refresh:** `ApiClient` shares one refresh across concurrent 401s, uses a separate Dio client with no interceptors, handles the rotating single-use refresh token (including "another request already refreshed"), and keeps the session on offline or timeout.
- **Session end:** logout revokes the refresh token best-effort and still works offline. Password change ends the local session and routes to "Password updated". Account deletion ends the session without a revoke call.
- **Error handling:** branches on `code`, uses the server's `message_en` / `message_ar`, maps field errors under the right form field, and does not leak raw exceptions.
- **Logging:** debug-only. Passwords, tokens and `avatar_base64` are masked, and request headers and bodies are not logged except for allow-listed endpoints.
- **Validation mirrors the server:** 8-character password minimum, passwords sent untrimmed, email trimmed, balance date window (today back to 5 years), avatar 5 MB check, plan names trimmed and compared exactly.
- **Plans and Compare:** archived plans excluded from the compare picker, same-plan selection blocked client-side, Base Plan archive/delete guarded.
- **Platform config:** only the `INTERNET` permission, no cleartext traffic, and the iOS photo-library usage string is present.

---

## 6. Suggested fix order

1. **H1** (income direction) and **H4** (remove demo/synthetic fallbacks, or show a clear "estimate" / error state).
2. **H2** and **H3** together (derive set-up completion from the server; flip `rememberAppFlow`).
3. **H6** (validate or fall back from a stale selected plan).
4. **H5** (correct the privacy text, add policy and terms links).
5. Medium items **M1–M7**, then low items and dead-code removal.

---

## 7. Pre-launch checklist for the developer (release signing and app identity)

Deferred by decision on 2026-10-17. All of this must be done before the final store release.

**Android**
1. Create an upload keystore and `android/key.properties` (`keyAlias`, `keyPassword`, `storeFile`, `storePassword`). Both are already git-ignored. Keep the keystore and passwords backed up safely; losing them blocks future updates.
2. Make the build fail instead of falling back to the debug key: in `android/app/build.gradle.kts`, throw a `GradleException` when `bundleRelease` is requested and `key.properties` is missing (keep the fallback for local `flutter run --release`).
3. Build the store bundle with `flutter build appbundle --release --obfuscate --split-debug-info=<dir>` and keep the `<dir>` symbol files for crash reports. Optionally enable R8 (`isMinifyEnabled`, `isShrinkResources`) only after testing a release build with every plugin (secure storage, share, file saver).
4. Verify the signed bundle (`apksigner` / Play App Signing) is not signed with the debug key.

**App identity (both platforms)**
5. Choose the final reverse-domain app ID (placeholder today is `com.horizon.horizon`). Update Android `namespace` and `applicationId`, the `MainActivity` package folder, and the iOS `PRODUCT_BUNDLE_IDENTIFIER` (including `RunnerTests`). It cannot be changed after publishing.
6. Set the real app name, icon, version and build number (`pubspec.yaml` `version:` and `AppConstants.appVersion` must match).

**Store compliance**
7. Add and link a Terms of Service and a Privacy Policy (H5 deferred links): URLs in the signup text, in Settings, and in both store listings (`url_launcher` plus an Android `queries` entry for `https`).
8. iOS `PrivacyInfo.xcprivacy` (privacy manifest) and App Store privacy "nutrition labels": data collected = email, name, financial data, optional photo; linked to the user; not used for tracking. Also declare the required-reason APIs used by plugins (for example `UserDefaults`/SharedPreferences, file timestamps).
9. Google Play Data safety form with the same answers, and an account-deletion URL/flow statement (the in-app Delete account exists).
    Checked 2026-10-17: no `PrivacyInfo.xcprivacy` exists in `ios/`, and `Info.plist` has no `ITSAppUsesNonExemptEncryption` (set it to `false`; the app is HTTPS-only). Data to declare on both stores: email, display name, financial data and optional profile photo; linked to the user; no tracking; no analytics or ads SDKs; encrypted in transit; account deletion available in the app. Camera permission is not needed (gallery only). Android: only `INTERNET`, backups off.
10. Re-check the iOS Info.plist keys added for export (`UIFileSharingEnabled`, `LSSupportsOpeningDocumentsInPlace`) are acceptable for the listing.

**Before sending the build**
11. Run `flutter pub get`, `flutter analyze` and the full test suite (the audit fixes were made without running anything), then a manual release-mode pass on a real Android and iPhone: signup, set-up, login on a second device, export, logout.
