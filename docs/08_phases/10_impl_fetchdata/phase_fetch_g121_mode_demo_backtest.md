# Phase G121: Requirement Gap Closure (QF-041)

## Goal
- Close requirement gap `QF-041` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:80`.

## Requirements
- Requirement ID: QF-041
- Owner Track: impl_fetchdata
- Clause: mode: demo | backtest

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
- Implement the `QF-041` fetch-request contract so `mode` is accepted at request level and
  routed into runtime policy as the authoritative execution mode.
- Keep compatibility with existing runtime callers (`smoke|research`) while enforcing normalized
  policy modes and explicit conflict checks when `fetch_request.mode` and `policy.mode` disagree.
- Add deterministic runtime tests for `mode=demo`, mode conflict rejection, and invalid mode rejection.

### Execution Record
- Updated `src/quant_eam/qa_fetch/runtime.py`:
  - Added request-level `mode` merge handling (`fetch_request.mode -> policy.mode`).
  - Added normalized policy mode coercion with bounded mode set validation.
  - Added explicit conflict validation when wrapper mode and policy mode differ.
- Updated `tests/test_qa_fetch_runtime.py`:
  - Added `test_execute_fetch_by_intent_accepts_fetch_request_mode_demo`.
  - Added `test_execute_fetch_by_intent_rejects_conflicting_fetch_request_mode_and_policy_mode`.
  - Added `test_execute_fetch_by_intent_rejects_unsupported_policy_mode`.
- Updated SSOT writeback in `docs/12_workflows/skeleton_ssot_v1.yaml`:
  - `G121` set to `implemented`.
  - `QF-041` set to `implemented`.
  - `CL_FETCH_121` roll-up set to `implemented`.

### Acceptance Record
- `python3 scripts/check_docs_tree.py`
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py`
- `rg -n "G121|QF-041" docs/12_workflows/skeleton_ssot_v1.yaml`
