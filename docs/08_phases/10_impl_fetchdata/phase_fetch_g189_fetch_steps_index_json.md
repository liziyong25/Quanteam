# Phase G189: Requirement Gap Closure (QF-097)

## Goal
- Close requirement gap `QF-097` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:170`.

## Requirements
- Requirement ID: QF-097
- Owner Track: impl_fetchdata
- Clause: fetch_steps_index.json

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
### 1) Runtime clause anchor
- Add explicit QF-097 anchor in `src/quant_eam/qa_fetch/runtime.py`:
  `UI_FETCH_EVIDENCE_VIEWER_STEPS_INDEX_FILENAME`.
- Bind it to the canonical evidence artifact filename:
  `fetch_steps_index.json`.

### 2) Regression coverage
- Extend `tests/test_qa_fetch_runtime.py` with:
  `test_runtime_ui_fetch_evidence_viewer_steps_index_filename_anchor_matches_qf_097_clause`.
- Assert the QF-097 anchor equals both:
  - literal `fetch_steps_index.json`
  - runtime evidence constant `FETCH_EVIDENCE_STEPS_INDEX_FILENAME`

### 3) SSOT writeback
- Mark `G189` as `implemented`.
- Mark `QF-097` as `implemented`.
- Mark `CL_FETCH_189` as `implemented`.
- Mark linked interface contracts with `impl_requirement_id: QF-097` as `implemented`.

## Execution Record
- Date: 2026-02-14.
- Scope outcome:
  - Runtime now exposes an explicit QF-097 clause anchor for Fetch Evidence Viewer.
  - Runtime tests lock the QF-097 filename contract.
  - SSOT requirement-goal-cluster/interface linkage is written back to implemented state.

## Acceptance Record
- `python3 scripts/check_docs_tree.py`
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py`
- `rg -n "G189|QF-097" docs/12_workflows/skeleton_ssot_v1.yaml`
