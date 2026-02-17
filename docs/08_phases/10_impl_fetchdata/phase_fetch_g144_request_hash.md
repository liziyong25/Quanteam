# Phase G144: Requirement Gap Closure (QF-057)

## Goal
- Close requirement gap `QF-057` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:102`.

## Requirements
- Requirement ID: QF-057
- Owner Track: impl_fetchdata
- Clause: request_hash（复现与缓存键）

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
1. Runtime meta contract hardening:
   - Updated `src/quant_eam/qa_fetch/runtime.py` to anchor QF-057 with
     `FETCH_RESULT_META_REQUEST_HASH_FIELD = "request_hash"`.
   - Updated `_build_fetch_meta_doc(...)` to write the request hash through the
     QF-057 anchor key while preserving canonical hash behavior.
2. Regression coverage:
   - Added
     `tests/test_qa_fetch_runtime.py::test_runtime_fetch_result_meta_request_hash_field_anchor_matches_qf_057_clause`
     to lock the QF-057 field contract.
   - Added
     `tests/test_qa_fetch_runtime.py::test_runtime_request_hash_is_canonical_for_equivalent_payloads`
     to enforce deterministic hash reproducibility for equivalent request payloads.
3. SSOT writeback:
   - Updated `docs/12_workflows/skeleton_ssot_v1.yaml` to mark `G144`,
     `QF-057`, `CL_FETCH_144`, and linked interface contracts as implemented.

## Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py` passed.
- `rg -n "G144|QF-057" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
