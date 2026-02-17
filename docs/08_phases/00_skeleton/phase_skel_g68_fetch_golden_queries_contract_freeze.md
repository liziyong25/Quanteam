# Phase Skeleton G68: QA Fetch Golden Queries Contract Freeze

## 1) Goal
Freeze golden-query manifest and summary contract for unattended fetch regression governance.

## 2) Requirements
- MUST define deterministic hash identity rules for query requests.
- MUST define append-only summary semantics.
- MUST remain documentation-only in skeleton track.
- MUST NOT modify `contracts/**`, `policies/**`, or holdout visibility scope.

## 3) Architecture & Interfaces
- Inputs:
  - `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md` (section 6.4)
  - `Quant‑EAM Whole View Framework.md（v0.5‑draft）.md`
- Outputs:
  - `docs/05_data_plane/qa_fetch_golden_queries_v1.md`
  - `docs/08_phases/00_skeleton/phase_skel_g68_fetch_golden_queries_contract_freeze.md`

## 4) Out-of-scope
- Runtime/provider online fetch validation.
- Notebook execution workflow changes.
- Policy bundle modifications.

## 5) DoD
- `python3 scripts/check_docs_tree.py`
- `rg -n "G68|phase_skel_g68|golden_queries" docs/12_workflows/skeleton_ssot_v1.yaml`

## 6) Implementation Plan
### 6.1 Freeze Decisions
- Golden query identity is frozen as canonical request hash (`sha256` of sorted canonical JSON).
- Summary output is append-only governance evidence and sorted by `query_id`.
- This phase remains documentation-only.

### 6.2 Controller Execution Record
- Added canonical contract document: `docs/05_data_plane/qa_fetch_golden_queries_v1.md`.
- No runtime/provider/orchestrator behavior was modified.

### 6.3 Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `rg -n "G68|phase_skel_g68|golden_queries" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
