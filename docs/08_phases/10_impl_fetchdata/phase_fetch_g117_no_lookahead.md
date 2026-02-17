# Phase G117: Requirement Gap Closure (QF-033)

## Goal
- Close requirement gap `QF-033` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:61`.

## Requirements
- Requirement ID: QF-033
- Owner Track: impl_fetchdata
- Clause: no‑lookahead（防前视）；

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
- Enforce no-lookahead at runtime execution by pruning rows where `available_at > as_of`
  (when both timestamps are parseable), so returned payloads cannot include forward-looking rows.
- Preserve `as_of` from intent-style fetch requests so no-lookahead enforcement applies consistently
  in both `execute_fetch_by_name(...)` and `execute_fetch_by_intent(...)` paths.
- Lock behavior with focused runtime regression tests.

### Execution Record
- Updated `src/quant_eam/qa_fetch/runtime.py`:
  - Added execution-time no-lookahead filtering (`available_at<=as_of`) before status/result finalization.
  - Added helper utilities to compare `available_at` vs `as_of` across list/DataFrame payload shapes.
  - Extended fetch-request unwrapping/intent coercion to carry top-level/intent-level `as_of` into effective runtime kwargs.
- Updated `tests/test_qa_fetch_runtime.py`:
  - Added `test_execute_fetch_by_name_enforces_no_lookahead_filter`.
  - Added `test_execute_fetch_by_intent_enforces_no_lookahead_with_top_level_as_of`.
- SSOT alignment:
  - `docs/12_workflows/skeleton_ssot_v1.yaml` already contains `QF-033` in implemented state in this snapshot;
    no additional status flip was required for this execution.

### Acceptance Record
- `python3 scripts/check_docs_tree.py`
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py`
- `rg -n "G117|QF-033" docs/12_workflows/skeleton_ssot_v1.yaml`
