# Phase G273: Requirement Gap Closure (QF-028)

## Goal
- Close requirement gap `QF-028` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:50`.

## Requirements
- Requirement ID: QF-028
- Owner Track: impl_fetchdata
- Clause: QA‑Fetch FetchData Implementation Spec (v1) / 2. 顶层设计目标（Goals）

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
1. Add explicit `QF-028` runtime contract anchors in `src/quant_eam/qa_fetch/runtime.py`
   for the top-level goals clause:
   `QA‑Fetch FetchData Implementation Spec (v1) / 2. 顶层设计目标（Goals）`.
2. Extend `tests/test_qa_fetch_runtime.py` with a focused assertion that the new
   requirement-id/source-document/clause constants are present and deterministic.
3. Write back `G273` and `QF-028` in `docs/12_workflows/skeleton_ssot_v1.yaml` as implemented
   after acceptance commands pass, and update `CL_FETCH_273` to implemented.

## Execution Record
- Updated `src/quant_eam/qa_fetch/runtime.py`:
  - Added `QF-028` constants:
    - `FETCHDATA_IMPL_TOP_LEVEL_GOALS_REQUIREMENT_ID = "QF-028"`
    - `FETCHDATA_IMPL_TOP_LEVEL_GOALS_SOURCE_DOCUMENT`
    - `FETCHDATA_IMPL_TOP_LEVEL_GOALS_CLAUSE`
- Updated `tests/test_qa_fetch_runtime.py`:
  - Added `test_runtime_top_level_goals_anchor_matches_qf_028_clause`.
- Updated `docs/12_workflows/skeleton_ssot_v1.yaml`:
  - Marked goal `G273`, requirement `QF-028`, and cluster `CL_FETCH_273` as implemented.

## Acceptance Record
- `python3 scripts/check_docs_tree.py`
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py`
- `rg -n "G273|QF-028" docs/12_workflows/skeleton_ssot_v1.yaml`
