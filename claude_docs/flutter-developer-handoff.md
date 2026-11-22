# Flutter client (Horizon): developer hand-off checklist

**Date:** 2026-10-17
**Repo:** `PFMP-Flutter`
**Context:** the audit in `flutter-client-audit.md` was done by static code reading only. About 30 files were then changed in `PFMP-Flutter` (uncommitted). **Nothing was built, analyzed, run or tested.** Everything below is the work that still has to be done by a person with a machine and devices.

---

## A. First: get the changes building and green

1. Review the uncommitted diff (`git diff` in `PFMP-Flutter`, about 30 files), then commit it in logical pieces.
2. `flutter pub get`. Two packages were added without being resolved: `archive: ^4.0.7` and `file_saver: ^0.7.0`. If a version does not fit the SDK constraints, adjust it.
3. `flutter analyze`. Fix anything it reports. The edits were made by hand, including the generated localization files (`lib/core/localization/generated/`). If you prefer, regenerate them with `flutter gen-l10n` and check the diff is only formatting.
4. `flutter test`. Known tests that need repair or that I could not verify:
   - `test/modules/home/controllers/home_dashboard_controllers_test.dart`, "the dashboard uses the currency saved on the device": it reads the dashboard with no plan and no plan-service fake. It now needs `basePlanServiceProvider`, plan-transaction and forecast fakes, as `home_screen_test.dart` has.
   - `test/modules/home/screens/home_screen_test.dart`: "a plan only the API knows, without a forecast, shows as 'Scenario'" sets `forecasts.failing = true`. The Home dashboard now shows an error screen when the forecast fails, so it may no longer find the plan pill. Also check the Compare tests that set `forecasts.failing = true`.
   - `test/modules/splash/screens/splash_screen_test.dart`: a signed-in splash now calls `validateSelection()` (a `GET /scenarios`). Override `basePlanServiceProvider` with `FakeBasePlanService` so it does not reach the network.
   - `test/modules/settings/settings_data_test.dart`: the export tests were rewritten. The helper that builds a ZIP assumes the `archive` 4.x API (`ArchiveFile.bytes`, non-null `ZipEncoder().encode`). Adjust if it does not compile.
   - `test/modules/account_setup/setup_flow_test.dart`: `transactions.list` is now stubbed. Check the income and plan steps still pass with the new "check the server first" calls.
5. Add tests that do not exist yet:
   - Login sets `accountSetupDone` before the session starts (`login_controller.dart`).
   - `BasePlanController.validateSelection()`: selected plan missing falls back to Base, still present refreshes, offline keeps the saved one.
   - Set-up income skipped when the same item is already on the Base Plan; set-up plans only send names that do not exist yet.
   - `_dashboardFor`: no plan, no balance, forecast failure and this-month-items failure each give an error, never demo data.
   - `remove()` reloads the lists when its second call fails.
6. Existing accounts: anyone who completed set-up before the income fix has their set-up salary stored as an **expense**. Fix those rows by hand (or with a one-off script).

---

## B. What changed (so you know what to look at)

| Area | Change |
|---|---|
| Set-up income | Sent as `income` (was `expense`). Skipped if an identical item already exists on the Base Plan. |
| Set-up plans | Only names that do not exist yet are sent (retry-safe). |
| Set-up amounts | Balance and income fields capped at 9 integer digits plus 2 decimals. |
| Login | Marks set-up as done before the session starts, so returning users skip the wizard. Sign-up still opens the wizard. |
| App start | `rememberAppFlow = true`: users stay signed in. |
| Splash | For signed-in users it calls `validateSelection()` (5 s cap): if the saved selected plan is gone, the Base Plan is used. |
| Home dashboard | No demo data, no estimated charts. A missing plan (reloaded first), balance, forecast or this-month items shows the error screen with Retry. |
| Transactions | "Remove from this plan" on a Modified row reloads the lists even if its second call fails. |
| Parsing | `PlanTransaction.fromJson` required fields and `ForecastMonth.month` are strict (throw `FormatException`). |
| Routes | `/setup/*` and `/ready` need a signed-in session. `/paywall` and `/password-updated` stay public. |
| Export | Individual files named `horizon-<table>-YYYY-MM-DD_HH-mm-ss.csv` (CSV: the server's ZIP is unpacked in the app) or `horizon-export-<stamp>.json`. Saved to `Download/Horizon` on Android and to the app's Documents folder (shown in the Files app) on iOS. The share sheet is used only if saving fails. Nothing is deleted afterwards. `Info.plist` got `UIFileSharingEnabled` and `LSSupportsOpeningDocumentsInPlace`. |
| Text | Onboarding privacy note no longer says "stays on your device". Set-up schedule notes say "starting today". The CSV export description no longer says ZIP. |

---

## C. Manual test plan (real Android and real iPhone, English and Arabic)

**Account and set-up**
1. New sign-up, then the 5-step wizard. On the Base Plan, the first income appears as **income** (positive in the forecast).
2. Enter more than 9 digits in the balance and income fields: it is blocked.
3. Kill the app right after the income step, reopen: you resume the wizard. Re-enter the same income and finish: only **one** salary row exists on the Base Plan.
4. On the last step, cut the network just as you tap Finish, then retry: no `scenario.name_taken` error and no duplicated plans.
5. Log out and log in on the same phone, and log in on a second phone: both go straight to Home with no wizard and no changed balance.
6. Sign up, quit mid-wizard, log in again: you land on an empty Home (known trade-off; balance and income can be added from Settings).

**Staying signed in and errors**
7. Cold start while signed in: still signed in, Home loads (no sign-in screen).
8. Cold start in airplane mode: Home shows an error with Retry, never "SAR 72,400" or invented charts. Reconnect and tap Retry: real data loads.
9. Make the forecast fail (block `/forecast` in a proxy or stop the backend route): Home, Forecast and Compare show an error, not estimated numbers.
10. On phone B delete (or archive) the plan that phone A has selected. Relaunch phone A: it opens on the Base Plan, not a 404 error loop.
11. Open `/setup/goals` or `/ready` while signed out (deep link): you are sent to Login.

**Transactions and plans**
12. On a derived plan, take a Modified row and use "Remove from this plan"; repeat with the network cut between the two calls: the list refreshes and the row shows as inherited.
13. Plans tab, Compare, Forecast and the plan switcher still work (create, rename, archive, unarchive, duplicate, delete).
14. Add, edit and delete transactions on the Base Plan and on a derived plan.

**Export (most changed)**
15. Android 10+: export JSON, and export CSV. Files appear in `Download/Horizon` with the date and time in their names. CSV gives 5 separate files (account, categories, scenarios, transactions, overlays) that open in a spreadsheet app.
16. Export twice: the files are not overwritten (different time stamps).
17. Android 9 or older (if you support it): saving needs a runtime permission, so the app falls back to the share sheet. Confirm it works.
18. iPhone: after export, the files are visible in Files, On My iPhone, Horizon.
19. Log out and delete the account: the exported files are still on the device.

**Settings and misc**
20. Change password (ends the session and shows "Password updated"), change currency, change language (RTL layout in Arabic), change cash balance, edit profile photo, Reset data, Delete account.
21. Read the onboarding privacy note and the set-up income schedule note in both languages.
22. Release-mode pass on both platforms (see section D) after the above passes in debug.

---

## D. Release preparation (deferred; must be done before the final store build)

**Android signing and build**
1. Create an upload keystore and `android/key.properties` (`keyAlias`, `keyPassword`, `storeFile`, `storePassword`). Both are already git-ignored. Back them up safely.
2. In `android/app/build.gradle.kts`, make a release bundle fail when `key.properties` is missing (today it silently signs with the debug key). Keep the fallback for local `flutter run --release`.
3. Build with `flutter build appbundle --release --obfuscate --split-debug-info=<dir>` and keep the symbol files for crash reports. Turn R8 on (`isMinifyEnabled`, `isShrinkResources`) only after testing a release build with every plugin (secure storage, share, file saver).
4. Verify the final bundle is not debug-signed.

**App identity (both platforms)**
5. Choose the final reverse-domain app ID (placeholder: `com.horizon.horizon`). Update the Android `namespace` and `applicationId`, the `MainActivity` package folder, and the iOS `PRODUCT_BUNDLE_IDENTIFIER` (including `RunnerTests`). It cannot be changed after publishing.
6. Set the real app name, icon, version and build number (`pubspec.yaml` `version:` and `AppConstants.appVersion` must match).

**Store compliance**
7. Write and host a Terms of Service and a Privacy Policy. Link them from the signup text, from Settings and from both store listings (add `url_launcher` plus an Android `queries` entry for `https`).
8. iOS: add `ios/Runner/PrivacyInfo.xcprivacy` (privacy manifest, with the required-reason APIs the plugins use, for example `UserDefaults`) and add it to the Runner target. Add `ITSAppUsesNonExemptEncryption` = `false` to `Info.plist` (the app is HTTPS-only).
9. Fill in the App Store privacy labels and the Google Play Data safety form. Data collected: email, display name, financial data (balances, transactions) and an optional profile photo. All of it is linked to the user. No tracking, no analytics or ad SDKs, encrypted in transit, and account deletion is available in the app.
10. Confirm the two iOS `Info.plist` keys added for export (`UIFileSharingEnabled`, `LSSupportsOpeningDocumentsInPlace`) are acceptable for the listing.
11. Camera permission is not needed (gallery only). Android needs only `INTERNET`, and backups are already off.

---

## E. Deferred by decision (not required for phase 1; keep for later)

| Item | Note |
|---|---|
| Currency mismatch for a new account on a used phone (M1) | Rare. Fix: always send `PATCH /me/settings` in `CurrencyController.change()` when signed in. |
| Language not synced with the account (M5) | The backend never reads `Accept-Language`, and the stored `locale` is only used by the export. Fix: apply `GET /me` `locale` when the device has no saved language. |
| Arabic keyboards and `\d` (L4) | Add a formatter that maps Eastern Arabic digits and `٫`/`،` to ASCII. Also fix the edit-transaction regex `^\d{0,9}\.?\d{0,2}` to `^\d{0,9}(\.\d{0,2})?`. |
| Avatar disk cache survives sign-out | Evict the user's avatar with `CachedNetworkImage.evictFromCache(url)` on sign-out. |
| Certificate pinning (L2) | Decided out for phase 1. Revisit before bank connections or payments. |
| Dead code (L6) | The `/products` sample (`HomeController`, `HomeItem*`, `/items/:id`) is safe to delete. `homeCreatedPlansProvider` looks unused. `homePlanEditsProvider` is still live. `homeBaseTxEditsProvider` is only used in the now-unreachable demo branch of `home_edit_transaction_screen.dart`. Keep the paywall and subscription code for phase 2. |
| Flutter copy of `API-ENDPOINTS.md` §6 (L7) | Stale (name as a string; the backend now takes a list). No impact. Copy the backend's version over. |
| Delete account and Reset data without a password (L8) | Next phase: enforce `current_password` on `DELETE /me` and `DELETE /me/data` in the backend and add a password field to both dialogs. |
| Safety net for a plan deleted while the app runs | On `scenario.not_found` for the selected plan, reselect the Base Plan and reload. |
| Wizard resume | A user who quits mid-wizard and logs in again skips the rest of set-up. A server-side "set-up completed" flag would fix it. |
| Terms and Privacy Policy links | See D7. |
| Out of scope on purpose | Set-up goals (static), subscription and paywall (next phase). |

---

## F. Backend reference

- Live API: `https://api-finance-forecast.com/v1`. 281 backend tests passed when last checked (run with the venv on `PATH`, because the suite shells out to `alembic`).
- The Flutter client calls 29 of the 33 documented endpoints. Not used by design: `GET /scenarios/{id}` and `POST/PATCH/DELETE /categories`. `GET /health` and `GET /health/db` are for monitoring.
