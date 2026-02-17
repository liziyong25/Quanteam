# Phase G127: Requirement Gap Closure (QF-045)

## Goal
- Close requirement gap `QF-045` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:85`.

## Requirements
- Requirement ID: QF-045
- Owner Track: impl_fetchdata
- Clause: fields（可选，技术指标默认 OHLCV）

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
- Add an explicit runtime clause anchor for QF-045 so `fields` default behavior is machine-checkable.
- Extend fetch-intent payload coercion to accept `fields` from nested intent or top-level wrapper.
- Normalize `fields` input deterministically and support `OHLCV` alias expansion.
- Default intent-path execution `fields` to OHLCV when user input omits `fields`.
- Add runtime tests to lock defaulting, alias behavior, and invalid selector rejection.

### Execution Record
- Updated `src/quant_eam/qa_fetch/runtime.py`:
  - Added `INTENT_DEFAULT_FIELDS_OHLCV` as QF-045 clause anchor.
  - Added `fields` to `FetchIntent` and intent evidence payload serialization.
  - Added deterministic fields selector coercion with `OHLCV` alias expansion.
  - Updated intent-wrapper unwrapping to merge/forward `fields`.
  - Updated intent effective kwargs so intent-path execution defaults `fields` to OHLCV when omitted.
- Updated `tests/test_qa_fetch_runtime.py`:
  - Added `test_runtime_intent_default_fields_anchor_matches_qf_045_clause`.
  - Added `test_execute_fetch_by_intent_defaults_fields_to_ohlcv`.
  - Added `test_execute_fetch_by_intent_accepts_fields_ohlcv_alias`.
  - Added `test_execute_fetch_by_intent_rejects_invalid_intent_fields_selector`.
- Updated `docs/12_workflows/skeleton_ssot_v1.yaml`:
  - `G127` set to `implemented`.
  - `QF-045` set to `implemented`.
  - `CL_FETCH_127` roll-up set to `implemented`.

### Acceptance Record
- `python3 scripts/check_docs_tree.py`
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py`
- `rg -n "G127|QF-045" docs/12_workflows/skeleton_ssot_v1.yaml`
