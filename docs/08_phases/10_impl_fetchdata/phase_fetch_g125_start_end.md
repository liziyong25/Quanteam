# Phase G125: Requirement Gap Closure (QF-044)

## Goal
- Close requirement gap `QF-044` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:84`.

## Requirements
- Requirement ID: QF-044
- Owner Track: impl_fetchdata
- Clause: start, end

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
- Add an explicit runtime clause anchor for QF-044 so `start/end` intent requirements are machine-checkable.
- Enforce intent-mode window preconditions in runtime before resolver dispatch:
  - `start` and `end` must be non-empty.
  - when comparable, `start <= end`.
- Keep function-override mode unchanged, because not every direct function call requires a date window.
- Update runtime tests to lock QF-044 semantics and keep existing universe/venue alias tests valid by passing explicit windows.

### Execution Record
- Updated `src/quant_eam/qa_fetch/runtime.py`:
  - Added `INTENT_REQUIRED_WINDOW_FIELDS = ("start", "end")` as the QF-044 clause anchor.
  - Added `_enforce_required_intent_window(...)` and integrated it in `execute_fetch_by_intent(...)` for intent-path execution.
  - Added normalized window-bound handling and deterministic `start <= end` guard.
- Updated `tests/test_qa_fetch_runtime.py`:
  - Added `test_runtime_intent_window_fields_anchor_matches_qf_044_clause`.
  - Added `test_execute_fetch_by_intent_rejects_missing_required_start_end_window`.
  - Added `test_execute_fetch_by_intent_rejects_start_after_end_window`.
  - Updated universe/venue intent tests to include explicit `start/end` window fields.
- Updated `docs/12_workflows/skeleton_ssot_v1.yaml`:
  - `G125` set to `implemented`.
  - `QF-044` set to `implemented`.
  - `CL_FETCH_125` roll-up set to `implemented`.

### Acceptance Record
- `python3 scripts/check_docs_tree.py`
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py`
- `rg -n "G125|QF-044" docs/12_workflows/skeleton_ssot_v1.yaml`
