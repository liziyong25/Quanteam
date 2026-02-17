# Phase Skeleton G74: Auto-Symbols Planner Contract Freeze

## 1) Goal
Freeze deterministic list-sample-day planner contract for `auto_symbols=true` fetch requests.

## 2) Requirements
- MUST define trigger and required planner-step sequence.
- MUST define deterministic step evidence naming and ordering.
- MUST remain documentation-only in skeleton track.
- MUST NOT modify `contracts/**`, `policies/**`, or holdout visibility scope.

## 3) Architecture & Interfaces
- Inputs:
  - `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md` (sections 5.1, 9)
  - `Quant‑EAM Whole View Framework.md（v0.5‑draft）.md` (FetchPlanner requirements)
- Outputs:
  - `docs/05_data_plane/qa_fetch_autosymbols_planner_contract_v1.md`
  - `docs/08_phases/00_skeleton/phase_skel_g74_fetch_autosymbols_planner_contract_freeze.md`

## 4) Out-of-scope
- Runtime planner code.
- Provider routing rewrites.
- UI workflow behavior changes.

## 5) DoD
- `python3 scripts/check_docs_tree.py`
- `rg -n "G74|auto_symbols|list->sample->day|step_001|step_002|step_003" docs/12_workflows/skeleton_ssot_v1.yaml docs/05_data_plane/qa_fetch_autosymbols_planner_contract_v1.md`

## 6) Implementation Plan
### 6.1 Freeze Decisions
- Added `docs/05_data_plane/qa_fetch_autosymbols_planner_contract_v1.md` to freeze deterministic planner trigger and ordered list-sample-day steps.
- Frozen step evidence naming:
  - `step_001_*` for list
  - `step_002_*` for sample
  - `step_003_*` for day
- Clarified canonical quartet maps to final (`day`) step outputs.

### 6.2 Controller Execution Record
- Published packet task card: `artifacts/subagent_control/G74/task_card.yaml`.
- Executed documentation-only skeleton scope; no runtime/provider code mutations.

### 6.3 Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `rg -n "G74|auto_symbols|list->sample->day|step_001|step_002|step_003" docs/12_workflows/skeleton_ssot_v1.yaml docs/05_data_plane/qa_fetch_autosymbols_planner_contract_v1.md` passed.
- `python3 scripts/check_subagent_packet.py --phase-id G74` passed via packet runner finish lifecycle.
