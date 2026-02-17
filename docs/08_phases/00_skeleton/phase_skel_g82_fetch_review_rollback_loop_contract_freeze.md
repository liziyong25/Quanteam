# Phase Skel G82: Fetch Review Rollback Loop Contract Freeze

## 1) Goal
Freeze fetch review failure -> rollback -> rerun -> re-review interaction contract and required evidence paths.

## 2) Requirements
- MUST define deterministic interaction sequence for reject/rollback/rerun/re-review.
- MUST define append-only evidence requirements for reject/rerun plus fetch viewer artifacts.
- MUST remain documentation-only.
- MUST NOT modify `contracts/**`, `policies/**`, or holdout visibility scope.

## 3) Architecture & Interfaces
- Inputs:
  - `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md` section 7.2 / DoD #4
  - existing reject/rerun API+UI semantics
- Outputs:
  - frozen rollback-loop contract doc

## 4) Out-of-scope
- Runtime/provider data logic changes.
- Policy/gate changes.
- UI implementation changes.

## 5) DoD
- `python3 scripts/check_docs_tree.py`
- `rg -n "G82|review|rollback|rerun|re-review|fetch evidence viewer" docs/12_workflows/skeleton_ssot_v1.yaml docs/05_data_plane/qa_fetch_review_rollback_loop_contract_v1.md`

## 6) Implementation Plan
### 6.1 Execution Strategy
- Add an interaction contract document that freezes sequence semantics and evidence locations.
- Keep the contract implementation-facing for immediate integration-test landing in impl goal.

### 6.2 Controller Execution Record
- Published packet task card: `artifacts/subagent_control/G82/task_card.yaml`.
- Added contract document:
  - `docs/05_data_plane/qa_fetch_review_rollback_loop_contract_v1.md`

### 6.3 Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `rg -n "G82|review|rollback|rerun|re-review|fetch evidence viewer" docs/12_workflows/skeleton_ssot_v1.yaml docs/05_data_plane/qa_fetch_review_rollback_loop_contract_v1.md` passed.
- `python3 scripts/check_subagent_packet.py --phase-id G82` passed via packet finish lifecycle.
