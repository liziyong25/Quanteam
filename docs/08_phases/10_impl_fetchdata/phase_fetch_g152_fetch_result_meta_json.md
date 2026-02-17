# Phase G152: Requirement Gap Closure (QF-064)

## Goal
- Close requirement gap `QF-064` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:113`.

## Requirements
- Requirement ID: QF-064
- Owner Track: impl_fetchdata
- Clause: fetch_result_meta.json

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
   - Add a QF-064 clause anchor in `src/quant_eam/qa_fetch/runtime.py`:
     `FETCH_EVIDENCE_RESULT_META_FILENAME = "fetch_result_meta.json"`.
   - Route `write_fetch_evidence(...)` to emit the canonical result-meta artifact
     via this anchor constant.
2. Regression coverage:
   - Add
     `tests/test_qa_fetch_runtime.py::test_runtime_fetch_evidence_result_meta_filename_anchor_matches_qf_064_clause`
     to lock the QF-064 filename contract.
   - Extend failure-path evidence coverage to assert
     `fetch_result_meta.json` is still persisted via the anchor constant when
     status is `error_runtime`.
3. SSOT alignment:
   - Keep `docs/12_workflows/skeleton_ssot_v1.yaml` unchanged in this pass.

## Acceptance Record
- `python3 scripts/check_docs_tree.py` passed (`docs tree: OK`).
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py` passed (`77 passed, 32 warnings`).
- `rg -n "G152|QF-064" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
