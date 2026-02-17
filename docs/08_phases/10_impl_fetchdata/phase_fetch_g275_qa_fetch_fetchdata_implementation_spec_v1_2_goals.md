# Phase G275: Requirement Gap Closure (QF-029)

## Goal
- Close requirement gap `QF-029` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:51`.

## Requirements
- Requirement ID: QF-029
- Owner Track: impl_fetchdata
- Clause: QA‑Fetch FetchData Implementation Spec (v1) / 2. 顶层设计目标（Goals） / G1 单一取数通道（Single Data Access Channel）

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
1. Add explicit `QF-029` runtime contract anchors in `src/quant_eam/qa_fetch/runtime.py`
   for the single-data-access-channel goals clause:
   `QA‑Fetch FetchData Implementation Spec (v1) / 2. 顶层设计目标（Goals） / G1 单一取数通道（Single Data Access Channel）`.
2. Extend `tests/test_qa_fetch_runtime.py` with a focused assertion that the new
   requirement-id/source-document/clause constants are present and deterministic.
3. Write back `G275` and `QF-029` in `docs/12_workflows/skeleton_ssot_v1.yaml` as implemented
   after acceptance commands pass, and update `CL_FETCH_275` to implemented.

## Execution Record
- Updated `src/quant_eam/qa_fetch/runtime.py`:
  - Added `QF-029` constants:
    - `FETCHDATA_IMPL_SINGLE_DATA_ACCESS_CHANNEL_REQUIREMENT_ID = "QF-029"`
    - `FETCHDATA_IMPL_SINGLE_DATA_ACCESS_CHANNEL_SOURCE_DOCUMENT`
    - `FETCHDATA_IMPL_SINGLE_DATA_ACCESS_CHANNEL_CLAUSE`
- Updated `tests/test_qa_fetch_runtime.py`:
  - Added `test_runtime_single_data_access_channel_anchor_matches_qf_029_clause`.
- Updated `docs/12_workflows/skeleton_ssot_v1.yaml`:
  - Marked goal `G275`, requirement `QF-029`, and cluster `CL_FETCH_275` as implemented.

## Acceptance Record
- `python3 scripts/check_docs_tree.py`
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py`
- `rg -n "G275|QF-029" docs/12_workflows/skeleton_ssot_v1.yaml`
