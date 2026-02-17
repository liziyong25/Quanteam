# Phase G160: Requirement Gap Closure (QF-069)

## Goal
- Close requirement gap `QF-069` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:120`.

## Requirements
- Requirement ID: QF-069
- Owner Track: impl_fetchdata
- Clause: step_XXX_fetch_request.json / step_XXX_fetch_result_meta.json / step_XXX_fetch_preview.csv / step_XXX_fetch_error.json

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
1. Runtime evidence filename anchoring:
   - Add QF-069 clause anchors in `src/quant_eam/qa_fetch/runtime.py` for:
     `step_{step_index:03d}_fetch_request.json`,
     `step_{step_index:03d}_fetch_result_meta.json`,
     `step_{step_index:03d}_fetch_preview.csv`,
     `step_{step_index:03d}_fetch_error.json`.
   - Route `write_fetch_evidence(...)` multi-step emission through the new
     anchors so step evidence filenames are deterministic and contract-bound.
2. Regression coverage:
   - Add a QF-069 anchor regression in `tests/test_qa_fetch_runtime.py` that
     locks all four step filename templates.
   - Update multi-step evidence assertions to use runtime anchors instead of
     hardcoded literals.
3. SSOT alignment:
   - Mark `G160`, `QF-069`, and `CL_FETCH_160` as `implemented` in
     `docs/12_workflows/skeleton_ssot_v1.yaml`.

## Acceptance Record
- `python3 scripts/check_docs_tree.py` passed (`docs tree: OK`).
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py` passed (`81 passed`).
- `rg -n "G160|QF-069" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
