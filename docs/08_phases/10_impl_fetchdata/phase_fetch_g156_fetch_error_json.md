# Phase G156: Requirement Gap Closure (QF-066)

## Goal
- Close requirement gap `QF-066` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:115`.

## Requirements
- Requirement ID: QF-066
- Owner Track: impl_fetchdata
- Clause: fetch_error.json（仅失败时，但失败必须有）

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
   - Add a QF-066 clause anchor in `src/quant_eam/qa_fetch/runtime.py`:
     `FETCH_EVIDENCE_ERROR_FILENAME = "fetch_error.json"`.
   - Route `write_fetch_evidence(...)` to emit single-step and multi-step error
     artifacts via the anchor constant.
2. Regression coverage:
   - Add
     `tests/test_qa_fetch_runtime.py::test_runtime_fetch_evidence_error_filename_anchor_matches_qf_066_clause`
     to lock the QF-066 filename contract.
   - Extend failure-path evidence assertions to validate `fetch_error.json` is
     persisted via the QF-066 anchor.
3. SSOT alignment:
   - Mark `G156`, `QF-066`, and `CL_FETCH_156` as `implemented` in
     `docs/12_workflows/skeleton_ssot_v1.yaml`.

## Acceptance Record
- `python3 scripts/check_docs_tree.py` passed (`docs tree: OK`).
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py` passed (`79 passed, 32 warnings`).
- `rg -n "G156|QF-066" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
