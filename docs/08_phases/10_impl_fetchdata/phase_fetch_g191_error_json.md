# Phase G191: Requirement Gap Closure (QF-099)

## Goal
- Close requirement gap `QF-099` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:172`.

## Requirements
- Requirement ID: QF-099
- Owner Track: impl_fetchdata
- Clause: 错误（error.json）

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
- Add explicit QF-099 anchor in `src/quant_eam/qa_fetch/runtime.py`:
  `UI_FETCH_EVIDENCE_VIEWER_ERROR_FILENAME`.
- Bind it to the canonical UI viewer filename:
  `error.json`.

### 2) Runtime evidence emission
- Keep existing failure evidence contracts unchanged:
  `fetch_error.json` and `step_XXX_fetch_error.json`.
- Extend `write_fetch_evidence(...)` to emit a deterministic top-level
  `error.json` alias for UI review whenever failure evidence exists.
- Ensure stale `error.json` is removed on non-failure runs.

### 3) Regression coverage
- Extend `tests/test_qa_fetch_runtime.py` with:
  `test_runtime_ui_fetch_evidence_viewer_error_filename_anchor_matches_qf_099_clause`.
- Extend failure-path evidence tests to assert `error.json` is emitted and
  content-equal to `fetch_error.json`.

### 4) SSOT writeback
- Mark `G191` as `implemented`.
- Mark `QF-099` as `implemented`.
- Mark `CL_FETCH_191` as `implemented`.
- Mark linked interface contracts with `impl_requirement_id: QF-099` as
  `implemented`.

## Execution Record
- Date: 2026-02-14.
- Scope outcome:
  - Runtime now exposes an explicit QF-099 UI filename anchor for error evidence.
  - Runtime emits top-level `error.json` on fetch failure without breaking
    existing `fetch_error.json` and step-level contracts.
  - Runtime tests lock the QF-099 filename and alias emission behavior.
  - SSOT requirement-goal-cluster/interface linkage is written back to
    implemented state.

## Acceptance Record
- `python3 scripts/check_docs_tree.py` passed (`docs tree: OK`).
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py` passed (`106 passed, 37 warnings`).
- `rg -n "G191|QF-099" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
