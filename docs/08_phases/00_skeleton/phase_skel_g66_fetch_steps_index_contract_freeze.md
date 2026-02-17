# Phase Skeleton G66: QA Fetch Steps Index Contract Freeze

## 1) Goal
Freeze `fetch_steps_index.json` contract semantics for deterministic multi-step fetch evidence review.

## 2) Requirements
- MUST define stable machine-readable fields for ordered step evidence.
- MUST preserve append-only step ordering semantics.
- MUST remain documentation-only in skeleton track.
- MUST NOT modify `contracts/**`, `policies/**`, or holdout visibility scope.

## 3) Architecture & Interfaces
- Inputs:
  - `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md` (section 4.2)
  - `Quant‑EAM Whole View Framework.md（v0.5‑draft）.md`
- Outputs:
  - `docs/05_data_plane/qa_fetch_steps_index_contract_v1.md`
  - `docs/08_phases/00_skeleton/phase_skel_g66_fetch_steps_index_contract_freeze.md`

## 4) Out-of-scope
- Runtime code changes for fetch emission.
- UI interaction redesign.
- Contract schema file modifications.

## 5) DoD
- `python3 scripts/check_docs_tree.py`
- `rg -n "G66|phase_skel_g66|steps_index" docs/12_workflows/skeleton_ssot_v1.yaml`

## 6) Implementation Plan
### 6.1 Freeze Decisions
- `fetch_steps_index.json` is mandatory for each fetch evidence bundle.
- Step records are append-only and ordered by `step_index`.
- Single-step runtime execution is represented as `step_kind=single_fetch`.

### 6.2 Controller Execution Record
- Added canonical contract document: `docs/05_data_plane/qa_fetch_steps_index_contract_v1.md`.
- Kept scope documentation-only (no runtime/provider code mutation).

### 6.3 Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `rg -n "G66|phase_skel_g66|steps_index" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
