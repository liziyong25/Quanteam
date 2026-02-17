# Phase G142: Requirement Gap Closure (QF-056)

## Goal
- Close requirement gap `QF-056` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:101`.

## Requirements
- Requirement ID: QF-056
- Owner Track: impl_fetchdata
- Clause: min_ts/max_ts

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
   - Updated `src/quant_eam/qa_fetch/runtime.py` to anchor QF-056 with
     `FETCH_RESULT_META_MIN_MAX_TS_FIELDS = ("min_ts", "max_ts")`.
   - Updated `_build_fetch_meta_doc(...)` to write `min_ts`/`max_ts`
     deterministically through the anchor tuple after extracting bounds from
     preview rows.
2. Regression coverage:
   - Added
     `tests/test_qa_fetch_runtime.py::test_runtime_fetch_result_meta_min_max_ts_fields_anchor_matches_qf_056_clause`
     to lock the QF-056 field contract.
3. SSOT writeback:
   - Updated `docs/12_workflows/skeleton_ssot_v1.yaml` to mark `G142`,
     `QF-056`, `CL_FETCH_142`, and linked interface contracts as implemented.

## Acceptance Record
- `python3 scripts/check_docs_tree.py` passed (`docs tree: OK`).
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py` passed (`70 passed`).
- `rg -n "G142|QF-056" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
