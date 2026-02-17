# Phase Skeleton G72: Fetch Dossier Evidence Viewer Contract Freeze

## 1) Goal
Freeze dossier-local fetch evidence and read-only viewer contract semantics for deterministic review checkpoints.

## 2) Requirements
- MUST define `artifacts/dossiers/<run_id>/fetch/` required artifacts and append-only behavior.
- MUST define read-only viewer behavior sourced from dossier fetch artifacts.
- MUST remain documentation-only in skeleton track.
- MUST NOT modify `contracts/**`, `policies/**`, or holdout visibility scope.

## 3) Architecture & Interfaces
- Inputs:
  - `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md` (sections 4.3, 7.1)
  - `Quant‑EAM Whole View Framework.md（v0.5‑draft）.md` (dossier + UI requirements)
- Outputs:
  - `docs/05_data_plane/qa_fetch_dossier_evidence_contract_v1.md`
  - `docs/08_phases/00_skeleton/phase_skel_g72_fetch_dossier_evidence_viewer_contract_freeze.md`

## 4) Out-of-scope
- Runtime dossier sync logic.
- UI route implementation details.
- Provider fetch execution logic.

## 5) DoD
- `python3 scripts/check_docs_tree.py`
- `rg -n "G72|dossier.*fetch|Fetch Evidence Viewer|fetch_steps_index" docs/12_workflows/skeleton_ssot_v1.yaml docs/05_data_plane/qa_fetch_dossier_evidence_contract_v1.md`

## 6) Implementation Plan
### 6.1 Freeze Decisions
- Added `docs/05_data_plane/qa_fetch_dossier_evidence_contract_v1.md` to freeze dossier-local fetch evidence layout.
- Frozen viewer contract requires read-only rendering from dossier `fetch_steps_index.json` and per-step evidence references.
- Clarified orchestrator sync rule from `jobs/<job_id>/outputs/fetch/` to `artifacts/dossiers/<run_id>/fetch/`.

### 6.2 Controller Execution Record
- Published packet task card: `artifacts/subagent_control/G72/task_card.yaml`.
- Executed documentation-only skeleton scope with no runtime/provider mutations.

### 6.3 Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `rg -n "G72|dossier.*fetch|Fetch Evidence Viewer|fetch_steps_index" docs/12_workflows/skeleton_ssot_v1.yaml docs/05_data_plane/qa_fetch_dossier_evidence_contract_v1.md` passed.
- `python3 scripts/check_subagent_packet.py --phase-id G72` passed via packet runner finish lifecycle.
