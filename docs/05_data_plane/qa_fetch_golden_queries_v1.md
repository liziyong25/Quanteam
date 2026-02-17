# QA Fetch Golden Queries v1

## Purpose

Define a deterministic golden-query manifest used by unattended fetch regression checks.

## Principles

- Golden queries validate request-shape stability first, not provider-side data variance.
- Query identity is derived from canonical request payload hash.
- Results are reported as append-only summaries for review checkpoints.

## Minimal Manifest Fields

- `schema_version`: `qa_fetch_golden_queries_v1`
- `queries`: non-empty array
  - `query_id`: stable identifier
  - `request`: fetch request object (intent/function wrapper allowed)
  - `expected_output`:
    - `status`
    - `request_hash` (optional; defaults to canonical request hash)
    - `row_count`
    - `columns`
  - `tags`: optional list of labels

## Output Summary Fields

- `schema_version`: `qa_fetch_golden_summary_v1`
- `generated_at`: UTC ISO-8601 timestamp
- `rule`: `fixed_query_set_with_expected_outputs`
- `requirement_id`: `QF-086`
- `total_queries`
- `query_hashes`: map `query_id -> sha256(canonical_request_json)`
- `expected_outputs`: map `query_id -> {status, request_hash, row_count, columns}`
- `query_outputs`: map `query_id -> {status, request_hash, row_count, columns}`
- `regression_status`: `no_regression | regression_detected`
- `regression_detected`: boolean
- `regression_query_ids`

## Drift Report Fields (QF-088)

- Drift comparison must emit a report file.
- Report output path is controller-defined and must stay readable by CI/nightly jobs.
- `schema_version`: `qa_fetch_golden_drift_report_v1`
- `rule`: `controller_defined_report_path_ci_nightly_readable`
- `requirement_id`: `QF-088`
- `drift_detected`: boolean
- `drift_status`: `no_drift | drift_detected`
- `baseline_summary_path` / `current_summary_path` / `report_path`
- `added_query_ids` / `removed_query_ids` / `changed_query_ids`
- `changed_query_hashes`: per-query baseline/current hash deltas
- `regression_status`: `no_regression | regression_detected`
- `regression_detected`: boolean
- `regression_query_ids`
- `regression_details`
- `overall_status`: `pass | fail`

## Governance

- Manifest and summary are contract-adjacent governance artifacts and must avoid `contracts/**` changes in this track.
- Runtime integration and script/test enforcement are handled by impl track goals.
- Freeze record: accepted by G68 unattended autopilot phase execution.
