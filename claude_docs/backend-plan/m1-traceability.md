# M1 Traceability Table

Maps every case in the signed M1 document (`claude_docs/milestone-1-final.md`,
Part 2 §18–29) to the exact test that proves it, per §9.2's deliverable
("a traceability table mapping each acceptance criterion... to the
specific test cases that prove it"). Hand-maintained, not generated —
no CI pipeline exists to keep a generated one honest (backend-plan/12
§1, the CI/coverage-gates decision), so a hand-maintained table that's
updated in the same commit as any test change is the honest version of
this deliverable for this build.

All paths are relative to `backend/`.

| Case | What it verifies | Test |
|---|---|---|
| 18.1 | No items entered | `tests/engine/fixtures/m1/18.1.json` |
| 18.2 | Projected balance going negative | `tests/engine/fixtures/m1/18.2.json` |
| 18.3 | Current Cash Balance unchanged by scheduled items | `tests/api/test_m1_balance_cases.py::test_m1_case_18_3_current_balance_is_not_changed_by_scheduled_items` |
| 18.4 | Updating the balance re-anchors the forecast | `tests/api/test_m1_balance_cases.py::test_m1_case_18_4_updating_balance_reanchors_the_forecast` |
| 18.5 | Stale balance leaves the anchor untouched | `tests/api/test_m1_balance_cases.py::test_m1_case_18_5_stale_balance_leaves_the_anchor_untouched` |
| 19.1 | One-time income inside the forecast | `tests/engine/fixtures/m1/19.1.json` |
| 19.2 | One-time item dated before the forecast starts | `tests/engine/fixtures/m1/19.2.json` |
| 19.3 | One-time item dated after the forecast period, at two horizons | `tests/engine/fixtures/m1/19.3_horizon12.json`, `19.3_horizon36.json` |
| 20.1 | Monthly income, no end date | `tests/engine/fixtures/m1/20.1.json` |
| 20.2 | Monthly item starting later than the forecast | `tests/engine/fixtures/m1/20.2.json` |
| 20.3 | Monthly item that started before the app was used | `tests/engine/fixtures/m1/20.3.json` |
| 21.1 | End date falling on an occurrence date (inclusive) | `tests/engine/fixtures/m1/21.1.json` |
| 21.2 | End date one day before an occurrence | `tests/engine/fixtures/m1/21.2.json` |
| 21.3 | Start and end date on the same day | `tests/engine/fixtures/m1/21.3.json` |
| 22.1 | Monthly on the 31st | `tests/engine/fixtures/m1/22.1.json` |
| 22.2 | Monthly on the 30th | `tests/engine/fixtures/m1/22.2.json` |
| 22.3 | Monthly on the 29th | `tests/engine/fixtures/m1/22.3.json` |
| 22.4 | Quarterly crossing a short month | `tests/engine/fixtures/m1/22.4.json` |
| 23.1 | Monthly on the 31st through a leap February | `tests/engine/fixtures/m1/23.1.json` |
| 23.2 | Yearly item dated 29 February, across leap/non-leap years | `tests/engine/fixtures/m1/23.2.json` |
| 23.3 | Monthly item starting 29 February | `tests/engine/fixtures/m1/23.3.json` |
| 24.1 | Weekly, including a five-payday month | `tests/engine/fixtures/m1/24.1.json` |
| 24.2 | Fortnightly | `tests/engine/fixtures/m1/24.2.json` |
| 24.3 | Quarterly, half-yearly and yearly from the same date | `tests/engine/fixtures/m1/24.3.json` |
| 25.1 | Base Plan result | `tests/api/test_m1_plan_cases.py::test_m1_case_25_1_base_plan_result` |
| 25.2 | A new plan with nothing changed | `tests/api/test_m1_plan_cases.py::test_m1_case_25_2_a_new_plan_with_nothing_changed` |
| 25.3 | Plan with an item added | `tests/api/test_m1_plan_cases.py::test_m1_case_25_3_plan_with_an_item_added` |
| 25.4 | Plan with an item removed | `tests/api/test_m1_plan_cases.py::test_m1_case_25_4_plan_with_an_item_removed` |
| 25.5 | Plan with an item changed to end early | `tests/api/test_m1_plan_cases.py::test_m1_case_25_5_plan_with_an_item_changed_to_end_early` |
| 25.6 | A realistic combined plan | `tests/api/test_m1_plan_cases.py::test_m1_case_25_6_a_realistic_combined_plan` |
| 25.7 | A Base Plan change flows into every plan | `tests/api/test_m1_plan_cases.py::test_m1_case_25_7_a_base_change_flows_into_every_plan` |
| 25.8 | Plan changes never affect the Base Plan | `tests/api/test_m1_plan_cases.py::test_m1_case_25_8_plan_changes_never_affect_the_base_plan` |
| 25.9 | Plan with a different Current Cash Balance | `tests/api/test_m1_plan_cases.py::test_m1_case_25_9_plan_with_a_different_current_cash_balance` |
| 25.10 | Base item changed, plan had inherited it | `tests/api/test_m1_plan_cases.py::test_m1_case_25_10_base_item_changed_plan_had_inherited_it` |
| 25.11 | Base item changed in a field the plan did not override (the critical case — 310,400, not 312,900) | `tests/api/test_m1_plan_cases.py::test_m1_case_25_11_base_item_changed_in_a_field_the_plan_did_not_override` |
| 25.12 | Base item deleted, plan had inherited it | `tests/api/test_m1_plan_cases.py::test_m1_case_25_12_base_item_deleted_plan_had_inherited_it` |
| 25.13 | Base item deleted, plan had changed it | `tests/api/test_m1_plan_cases.py::test_m1_case_25_13_base_item_deleted_plan_had_changed_it` |
| 25.14 | Base item deleted, plan had removed it | `tests/api/test_m1_plan_cases.py::test_m1_case_25_14_base_item_deleted_plan_had_removed_it` |
| 25.15 | Duplicate preserves inheritance and changes | `tests/api/test_m1_plan_cases.py::test_m1_case_25_15_duplicate_preserves_inheritance_and_changes` |
| 25.16 | Duplicating the Base Plan | `tests/api/test_m1_plan_cases.py::test_m1_case_25_16_duplicating_the_base_plan` |
| 25.17 | Archive and restore, with a Base change in between | `tests/api/test_m1_plan_cases.py::test_m1_case_25_17_archive_and_restore_with_a_base_change_in_between` |
| 26.1 | Comparing Base Plan against Buy House | `tests/api/test_m1_compare_and_misc_cases.py::test_m1_case_26_1_comparing_base_plan_against_buy_house` |
| 26.2 | What is driving the difference | `tests/api/test_m1_compare_and_misc_cases.py::test_m1_case_26_2_what_is_driving_the_difference` |
| 26.3 | Percentage where the baseline is zero | `tests/api/test_m1_compare_and_misc_cases.py::test_m1_case_26_3_percentage_where_the_baseline_is_zero` |
| 27.1 | The four forecast horizons | `tests/engine/fixtures/m1/27.1.json` |
| 27.2 | Changing the horizon does not change the figures | `tests/engine/test_forecast.py::test_m1_case_27_2_horizon_choice_does_not_change_shared_months` |
| 27.3 | Dashboard selected-period totals | `tests/api/test_m1_compare_and_misc_cases.py::test_m1_case_27_3_dashboard_selected_period_totals` |
| 28.1 | Changing currency does not convert amounts | `tests/api/test_m1_compare_and_misc_cases.py::test_m1_case_28_1_changing_currency_does_not_convert_amounts` |
| 29.1 | Everything balances (reconciliation) | `tests/engine/test_invariants.py::test_reconciliation_holds_across_varied_cases` (hand-picked) + `tests/engine/test_properties.py::test_reconciliation_property` (generated) |
| 29.2 | Results are repeatable (determinism) | `tests/engine/test_invariants.py::test_determinism_same_inputs_identical_output` (hand-picked) + `tests/engine/test_properties.py::test_determinism_property` (generated) |
| 29.3 | Plans stay separate (isolation) | `tests/services/test_scenario_resolver.py::test_isolation_arbitrary_overlays_on_one_scenario_never_affect_another` and `test_override_never_mutates_the_underlying_base_transaction_row` (hand-picked) + `test_isolation_property` (generated) |
| 29.4 | Comparisons are fully explained (driver completeness) | `tests/engine/test_invariants.py::test_driver_completeness_across_a_larger_diff` (hand-picked) + `tests/engine/test_properties.py::test_driver_completeness_property` (generated) |

**Coverage:** all 43 numbered cases (§18–28) plus all 4 integrity checks (§29) — 47 of 47. Nothing in Part 2 is outstanding.

**Not covered here, by design:** the client's own "independently verified test cases" (M1 §30) — the placeholder `tests/engine/fixtures/client/` directory is still empty, waiting on them; this table gets a row added per case the moment they arrive, same convention as everything above.
