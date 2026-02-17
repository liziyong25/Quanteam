# Phase G150: Requirement Gap Closure (QF-063)

## Goal
- Close requirement gap `QF-063` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:112`.

## Requirements
- Requirement ID: QF-063
- Owner Track: impl_fetchdata
- Clause: fetch_request.json

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
   - Add a QF-063 clause anchor in `src/quant_eam/qa_fetch/runtime.py`:
     `FETCH_EVIDENCE_REQUEST_FILENAME = "fetch_request.json"`.
   - Route `write_fetch_evidence(...)` to emit the request artifact through the
     anchor constant to keep the filename contract deterministic.
2. Regression coverage:
   - Add
     `tests/test_qa_fetch_runtime.py::test_runtime_fetch_evidence_request_filename_anchor_matches_qf_063_clause`
     to lock the QF-063 filename contract.
   - Extend failure-path evidence coverage to assert `fetch_request.json` is
     still written when status is `error_runtime`.
3. SSOT alignment:
   - Keep `docs/12_workflows/skeleton_ssot_v1.yaml` unchanged in this pass.

## Acceptance Record
- `python3 scripts/check_docs_tree.py` passed (`docs tree: OK`).
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py` passed (`76 passed`).
- `rg -n "G150|QF-063" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
