# QA Fetch Structural Sanity Checks Contract v1

## Purpose

Freeze deterministic structural sanity checks emitted by fetch runtime evidence so review/gate flows can validate data-shape quality without reading source code.

## Scope

Applied to each fetch evidence meta document (`fetch_result_meta.json` and per-step `step_XXX_fetch_result_meta.json`).

## Required Sanity Summary (`sanity_checks`)

- `timestamp_field`: selected timestamp-like field name from preview rows, or empty when unavailable.
- `timestamp_order_rule`: fixed rule text `timestamp_monotonic_increasing_and_no_duplicates_or_record_allow_rule`.
- `timestamp_duplicate_policy`: fixed policy text `no_duplicates_allowed` (default policy unless separately overridden/recorded).
- `timestamp_monotonic_non_decreasing`: boolean, true when preview timestamps are non-decreasing.
- `timestamp_duplicate_count`: integer count of duplicate timestamp values in preview.
- `timestamp_rule_satisfied`: boolean, true when monotonicity and duplicate constraints both pass under current policy.
- `missing_ratio_by_column`: object mapping preview column name -> missing ratio in `[0,1]`.
- `preview_row_count`: integer row count used for sanity computation.
- `empty_data_policy_rule`: fixed text `empty_data_semantics_consistent_with_policy_on_no_data`.
- `on_no_data_policy`: normalized policy mode (`error` / `pass_empty` / `retry`) extracted from request payload.
- `empty_data_expected_status` / `empty_data_observed_status`: present only for terminal no-data outcomes.
- `empty_data_semantics_consistent`: boolean, true when terminal no-data status matches `on_no_data_policy`.

## Determinism Rules

- Field selection and ratio computation MUST be deterministic on identical input preview.
- Missing ratio computation is preview-local and read-only (no imputation/mutation).
- Absence of timestamp field MUST NOT raise runtime errors; emit safe defaults.

## Compatibility

- Existing fetch status semantics (`pass_*`, `blocked_*`, `error_runtime`) remain unchanged.
- Sanity summary is additive metadata and must not alter fetch result payload.
