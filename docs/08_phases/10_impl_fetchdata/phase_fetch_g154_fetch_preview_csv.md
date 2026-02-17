# Phase G154: Requirement Gap Closure (QF-065)

## Goal
- Close requirement gap `QF-065` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:114`.

## Requirements
- Requirement ID: QF-065
- Owner Track: impl_fetchdata
- Clause: fetch_preview.csv

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
   - Add a QF-065 clause anchor in `src/quant_eam/qa_fetch/runtime.py`:
     `FETCH_EVIDENCE_PREVIEW_FILENAME = "fetch_preview.csv"`.
   - Route `write_fetch_evidence(...)` to emit the canonical single-step preview
     artifact via the anchor constant.
2. Regression coverage:
   - Add
     `tests/test_qa_fetch_runtime.py::test_runtime_fetch_evidence_preview_filename_anchor_matches_qf_065_clause`
     to lock the QF-065 filename contract.
   - Extend evidence persistence assertions to validate the preview artifact is
     written via the anchor constant in runtime and failure-path cases.
3. SSOT alignment:
   - Mark `G154`, `QF-065`, and `CL_FETCH_154` as `implemented` in
     `docs/12_workflows/skeleton_ssot_v1.yaml`.

## Acceptance Record
- `python3 scripts/check_docs_tree.py` passed (`docs tree: OK`).
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py` passed (`78 passed, 32 warnings`).
- `rg -n "G154|QF-065" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
