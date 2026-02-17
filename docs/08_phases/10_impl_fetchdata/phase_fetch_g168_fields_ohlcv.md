# Phase G168: Requirement Gap Closure (QF-080)

## Goal
- Close requirement gap `QF-080` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:139`.

## Requirements
- Requirement ID: QF-080
- Owner Track: impl_fetchdata
- Clause: 默认 fields 至少包含 OHLCV

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
- Add an explicit runtime clause anchor for QF-080 so the technical-indicator default-fields requirement is machine-checkable.
- Ensure intent execution computes effective kwargs (including default OHLCV fields) even on `function_override`/function-wrapper path.
- Extend runtime tests to lock the defaulting behavior and explicit-fields override behavior.
- Mark SSOT goal/requirement/cluster state as implemented for G168/QF-080 closure.

### Execution Record
- Updated `src/quant_eam/qa_fetch/runtime.py`:
  - Added `TECHNICAL_INDICATOR_MIN_FIELDS_OHLCV` as QF-080 clause anchor.
  - Updated `execute_fetch_by_intent` function-override branch to use `_intent_effective_kwargs(intent)`, ensuring default `fields` include OHLCV when omitted.
- Updated `tests/test_qa_fetch_runtime.py`:
  - Added `test_runtime_technical_indicator_min_fields_anchor_matches_qf_080_clause`.
  - Updated `test_execute_fetch_by_intent_accepts_function_wrapper` to assert default OHLCV fields are applied.
  - Added `test_execute_fetch_by_intent_function_wrapper_preserves_explicit_fields`.
- Updated `docs/12_workflows/skeleton_ssot_v1.yaml`:
  - Set `G168`, `QF-080`, and `CL_FETCH_168` to `implemented`.

### Acceptance Record
- `python3 scripts/check_docs_tree.py`
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py`
- `rg -n "G168|QF-080" docs/12_workflows/skeleton_ssot_v1.yaml`
