# Phase Skel G76: Fetch DataAccessFacade Boundary Contract Freeze

## 1) Goal
Freeze the single-channel fetch access boundary for agent execution paths using qa_fetch facade entry points.

## 2) Requirements
- MUST document facade entry points as the only allowed agent-facing fetch execution API.
- MUST explicitly forbid direct runtime/provider import paths in agent fetch code.
- MUST keep scope documentation-only.
- MUST NOT modify `contracts/**`, `policies/**`, or holdout visibility scope.

## 3) Architecture & Interfaces
- Inputs:
  - `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md` (G1 single data access channel)
  - `Quant‑EAM Whole View Framework.md（v0.5‑draft）.md` (DataAccessFacade + FetchPlanner boundary)
- Outputs:
  - frozen fetch boundary contract doc for implementation-phase enforcement

## 4) Out-of-scope
- Runtime/provider logic rewrites.
- Policy or contract schema changes.
- UI behavior changes.

## 5) DoD
- `python3 scripts/check_docs_tree.py`
- `rg -n "G76|DataAccessFacade|single data access channel|禁止直连|no direct provider" docs/12_workflows/skeleton_ssot_v1.yaml docs/05_data_plane/qa_fetch_dataaccess_facade_boundary_v1.md`

## 6) Implementation Plan
### 6.1 Execution Strategy
- Add a fetch-boundary contract document that explicitly defines allowed facade entry points and forbidden direct import paths.
- Keep wording implementation-facing so next impl goal can add code/tests directly from the same boundary.

### 6.2 Controller Execution Record
- Published packet task card: `artifacts/subagent_control/G76/task_card.yaml`.
- Added boundary contract document:
  - `docs/05_data_plane/qa_fetch_dataaccess_facade_boundary_v1.md`

### 6.3 Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `rg -n "G76|DataAccessFacade|single data access channel|禁止直连|no direct provider" docs/12_workflows/skeleton_ssot_v1.yaml docs/05_data_plane/qa_fetch_dataaccess_facade_boundary_v1.md` passed.
- `python3 scripts/check_subagent_packet.py --phase-id G76` passed via packet finish lifecycle.
