# Phase G271: Requirement Gap Closure (QF-027)

## Goal
- Close requirement gap `QF-027` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:46`.

## Requirements
- Requirement ID: QF-027
- Owner Track: impl_fetchdata
- Clause: `execute_fetch_by_name(...)`

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
1. Add explicit QF-027 runtime contract anchors in `src/quant_eam/qa_fetch/runtime.py` for
   `execute_fetch_by_name(...)`.
2. Extend `tests/test_qa_fetch_runtime.py` to assert the QF-027 requirement-id/source-document/clause
   constants and entrypoint binding.
3. Write back `G271` and `QF-027` in `docs/12_workflows/skeleton_ssot_v1.yaml` as implemented
   after acceptance commands pass.

## Execution Record
- Updated `src/quant_eam/qa_fetch/runtime.py`:
  - Added QF-027 constants:
    - `FETCHDATA_IMPL_RUNTIME_NAME_ENTRYPOINT_REQUIREMENT_ID = "QF-027"`
    - `FETCHDATA_IMPL_RUNTIME_NAME_ENTRYPOINT_SOURCE_DOCUMENT`
    - `FETCHDATA_IMPL_RUNTIME_NAME_ENTRYPOINT_CLAUSE` for the clause `execute_fetch_by_name(...)`
- Updated `tests/test_qa_fetch_runtime.py`:
  - Extended `test_runtime_name_entrypoint_matches_qf_027_clause` to assert all QF-027 runtime
    anchor constants and runtime binding.
- Updated `docs/12_workflows/skeleton_ssot_v1.yaml`:
  - Marked goal `G271`, requirement `QF-027`, and cluster `CL_FETCH_271` as implemented.

## Acceptance Record
- `python3 scripts/check_docs_tree.py`
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py`
- `rg -n "G271|QF-027" docs/12_workflows/skeleton_ssot_v1.yaml`
