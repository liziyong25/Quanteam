# Phase Skeleton G59: QA Fetch Evidence Spec Freeze

## 1) Goal
Freeze the canonical fetch evidence specification so every fetch execution emits auditable artifacts with stable paths and machine-readable semantics.

## 2) Requirements
- MUST define evidence as append-only artifacts for replay/audit.
- MUST preserve the evidence quartet semantics: `fetch_request.json`, `fetch_result_meta.json`, `fetch_preview.csv`, and `fetch_error.json` (when failed).
- MUST keep intent-first request representation compatible with runtime execution.
- SHOULD align evidence fields with probe/runtime/registry cross-check use cases.

## 3) Architecture & Interfaces
- Inputs:
  - `Quant‑EAM Whole View Framework.md（v0.5‑draft）.md`
  - `QA_Fetch_Integration_for_GPTPro.md`
  - `docs/05_data_plane/qa_fetch_probe_v3/probe_summary_v3_notebook_params.json`
- Outputs:
  - `docs/08_phases/00_skeleton/phase_skel_g59_fetch_evidence_spec_freeze.md`
  - SSOT goal entry for G59 with evidence freeze constraints
- Dependencies:
  - `G29` (implemented) probe evidence baseline
- Immutable constraints:
  - Evidence paths are append-only and contract-bound; no hidden in-memory-only result path.

## 4) Out-of-scope
- Probe runtime implementation changes.
- New provider onboarding.
- Frontend rendering changes.

## 5) DoD
- Executable commands:
  - `python3 scripts/check_docs_tree.py`
  - `rg -n "G59|phase_skel_g59|fetch_result_meta|fetch_error" docs/12_workflows/skeleton_ssot_v1.yaml`
- Expected artifacts:
  - `docs/08_phases/00_skeleton/phase_skel_g59_fetch_evidence_spec_freeze.md`
  - `docs/12_workflows/skeleton_ssot_v1.yaml`

## 6) Implementation Plan
### 6.1 Freeze Decisions
- Canonical evidence quartet is fixed to:
  - `fetch_request.json`
  - `fetch_result_meta.json`
  - `fetch_preview.csv`
  - `fetch_error.json` (emit only when failed)
- Evidence emission remains append-only and replay-auditable; no in-memory-only success path is allowed.
- Quartet paths are treated as runtime/probe shared contract inputs for G62+ implementation goals.

### 6.2 Controller Execution Record
- Updated `docs/05_data_plane/qa_fetch_smoke_evidence_v1.md` to formalize quartet semantics and failure-path behavior.
- Kept scope documentation-only; no runtime or provider code changes.

### 6.3 Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `rg -n "G59|phase_skel_g59|fetch_result_meta|fetch_error" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
