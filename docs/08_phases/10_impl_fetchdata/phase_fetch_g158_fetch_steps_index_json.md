# Phase G158: Requirement Gap Closure (QF-068)

## Goal
- Close requirement gap `QF-068` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:119`.

## Requirements
- Requirement ID: QF-068
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
1. Runtime evidence filename anchoring:
   - Add a QF-068 clause anchor in `src/quant_eam/qa_fetch/runtime.py`:
     `FETCH_EVIDENCE_STEPS_INDEX_FILENAME = "fetch_steps_index.json"`.
   - Route `write_fetch_evidence(...)` to emit the steps index artifact via the
     anchor constant.
2. Regression coverage:
   - Add
     `tests/test_qa_fetch_runtime.py::test_runtime_fetch_evidence_steps_index_filename_anchor_matches_qf_068_clause`
     to lock the QF-068 filename contract.
   - Update steps-index persistence assertions to reference the runtime anchor
     constant.
3. SSOT alignment:
   - Mark `G158`, `QF-068`, and `CL_FETCH_158` as `implemented` in
     `docs/12_workflows/skeleton_ssot_v1.yaml`.

## Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py` passed.
- `rg -n "G158|QF-068" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
