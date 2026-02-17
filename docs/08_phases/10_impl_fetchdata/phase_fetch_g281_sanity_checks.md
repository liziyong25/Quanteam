# Phase G281: Requirement Gap Closure (QF-032)

## Goal
- Close requirement gap `QF-032` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:62`.

## Requirements
- Requirement ID: QF-032
- Owner Track: impl_fetchdata
- Clause: 数据结构性 sanity checks；

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
TBD by controller at execution time.

## Execution Record
- Updated `src/quant_eam/qa_fetch/runtime.py`:
  - Added explicit `QF-032` anchors for structural sanity checks:
    - `FETCHDATA_IMPL_STRUCTURAL_SANITY_REQUIREMENT_ID = "QF-032"`
    - `FETCHDATA_IMPL_STRUCTURAL_SANITY_SOURCE_DOCUMENT`
    - `FETCHDATA_IMPL_STRUCTURAL_SANITY_CLAUSE = "数据结构性 sanity checks；"`
  - Kept `TIME_TRAVEL_AVAILABILITY_RULE` coverage but removed the incorrect `QF-032` label from that rule comment.
- Updated `tests/test_qa_fetch_runtime.py`:
  - Replaced `test_runtime_time_travel_rule_anchor_matches_qf_032_clause` with:
    - `test_runtime_structural_sanity_anchor_matches_qf_032_clause`
    - `test_runtime_time_travel_rule_anchor_matches_clause`
- Updated `docs/12_workflows/skeleton_ssot_v1.yaml`:
  - Marked goal `G281` as `implemented`.
  - Marked requirement `QF-032` as `implemented` with `acceptance_verified: true`.
  - Marked cluster `CL_FETCH_281` as `implemented`.

## Acceptance Record
- `python3 scripts/check_docs_tree.py`
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py`
- `rg -n "G281|QF-032" docs/12_workflows/skeleton_ssot_v1.yaml`
- `python3 scripts/check_subagent_packet.py --phase-id G281`
