# Phase G131: Requirement Gap Closure (QF-048)

## Goal
- Close requirement gap `QF-048` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:89`.

## Requirements
- Requirement ID: QF-048
- Owner Track: impl_fetchdata
- Clause: on_no_data: error | pass_empty | retry

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
### Execution Strategy
- Add an explicit runtime clause anchor for `QF-048` so `on_no_data: error | pass_empty | retry` is machine-checkable.
- Enforce strict runtime validation for `policy.on_no_data` with normalized values: `error`, `pass_empty`, `retry`.
- Implement deterministic retry semantics for `on_no_data=retry`:
  - retry only when outcome is no-data (`row_count == 0` or exception classified as `pass_empty`);
  - execute one retry (2 total attempts);
  - keep `error` and `pass_empty` semantics unchanged.
- Add targeted runtime tests for anchor, validation, and retry execution paths.

### Execution Record
- Updated `src/quant_eam/qa_fetch/runtime.py`:
  - Added `POLICY_ON_NO_DATA_OPTIONS` as the QF-048 clause anchor.
  - Added strict `policy.on_no_data` coercion/validation.
  - Implemented deterministic no-data retry loop (`on_no_data=retry`) with one retry attempt.
- Updated `tests/test_qa_fetch_runtime.py`:
  - Added `test_runtime_policy_on_no_data_anchor_matches_qf_048_clause`.
  - Added `test_execute_fetch_by_name_rejects_unsupported_on_no_data_policy`.
  - Added `test_runtime_status_on_empty_data_retry_succeeds_on_second_attempt`.
  - Added `test_runtime_status_on_empty_data_retry_exhausted_returns_pass_empty`.
- Updated `docs/12_workflows/skeleton_ssot_v1.yaml`:
  - Marked `G131` as implemented.
  - Marked `QF-048` as implemented.
  - Marked `CL_FETCH_131` roll-up as implemented.

### Acceptance Record
- `python3 scripts/check_docs_tree.py`
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py`
- `rg -n "G131|QF-048" docs/12_workflows/skeleton_ssot_v1.yaml`
