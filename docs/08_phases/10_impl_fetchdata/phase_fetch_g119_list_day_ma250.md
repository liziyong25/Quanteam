# Phase G119: Requirement Gap Closure (QF-037)

## Goal
- Close requirement gap `QF-037` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:67`.

## Requirements
- Requirement ID: QF-037
- Owner Track: impl_fetchdata
- Clause: `*_list` → 选择样本 → `*_day`（例如 MA250 年线用例）

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
- Implement `auto_symbols=true` runtime behavior in `execute_fetch_by_intent(...)` so requests
  with missing symbols deterministically execute `*_list -> sample -> *_day`.
- Keep sampling deterministic (`stable_first_n`, default `n=5`) and preserve append-only step
  evidence via `fetch_steps_index.json` with canonical quartet files mapped to the final `day` step.
- Add focused runtime regression tests for planner success and no-candidate failure semantics.

### Execution Record
- Updated `src/quant_eam/qa_fetch/runtime.py`:
  - Added runtime-native auto-symbols planner path inside `execute_fetch_by_intent(...)`.
  - Added deterministic list-function resolution, candidate extraction, sample selection, and final day execution.
  - Extended intent coercion/request-evidence payloads to carry `auto_symbols` and `sample`.
  - Extended fetch-result finalization to support multi-step `step_records` evidence emission.
- Updated `tests/test_qa_fetch_runtime.py`:
  - Added `test_execute_fetch_by_intent_auto_symbols_planner_emits_list_sample_day_steps`.
  - Added `test_execute_fetch_by_intent_auto_symbols_planner_no_candidates_returns_runtime_error`.

### Acceptance Record
- `python3 scripts/check_docs_tree.py`
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py`
- `rg -n "G119|QF-037" docs/12_workflows/skeleton_ssot_v1.yaml`
