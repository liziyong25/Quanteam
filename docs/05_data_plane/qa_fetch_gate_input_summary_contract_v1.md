# QA Fetch Gate Input Summary Contract v1

## Purpose

Freeze deterministic fetch metadata fields that provide auditable inputs for time-travel/no-lookahead and data-snapshot-integrity gate checks.

## Scope

Applies to fetch result meta documents:
- canonical: `fetch_result_meta.json`
- step-level: `step_XXX_fetch_result_meta.json`

## Required Metadata Field

- `gate_input_summary`:
  - `no_lookahead`:
    - `rule`: fixed text `available_at<=as_of`
    - `has_as_of`: boolean
    - `available_at_field_present`: boolean
    - `available_at_violation_count`: non-negative integer
  - `data_snapshot_integrity`:
    - `request_hash`: canonical request hash string
    - `preview_row_count`: non-negative integer
    - `timestamp_field`: selected timestamp-like field (empty string when unavailable)
    - `timestamp_order_rule`: fixed text `timestamp_monotonic_increasing_and_no_duplicates_or_record_allow_rule`
    - `timestamp_duplicate_policy`: fixed text `no_duplicates_allowed`
    - `timestamp_monotonic_non_decreasing`: boolean
    - `timestamp_duplicate_count`: non-negative integer
    - `timestamp_rule_satisfied`: boolean
    - `nonzero_missing_ratio_columns`: sorted array of columns whose missing ratio is greater than zero

## Determinism Rules

- Summary must be computed from request/preview-derived metadata only.
- Summary is additive metadata and must not change fetch execution status semantics.
- Missing/invalid timestamps must not fail fetch execution; emit safe fallback values.
