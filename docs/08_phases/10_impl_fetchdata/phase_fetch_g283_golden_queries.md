# Phase G283: Requirement Gap Closure (QF-033)

## Goal
- Close requirement gap `QF-033` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:63`.

## Requirements
- Requirement IDs: QF-033
- Owner Track: impl_fetchdata
- Clause[QF-033]: Golden Queries 回归与漂移报告（最小集）。

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.
- Bundling criterion: same owner track + same source document + same parent requirement + near-adjacent source lines.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
TBD by controller at execution time.

## Execution Record
- Updated `src/quant_eam/qa_fetch/runtime.py`:
  - Added explicit `QF-033` anchors for Golden Queries minimal-set requirement:
    - `FETCHDATA_IMPL_GOLDEN_QUERIES_REQUIREMENT_ID = "QF-033"`
    - `FETCHDATA_IMPL_GOLDEN_QUERIES_SOURCE_DOCUMENT`
    - `FETCHDATA_IMPL_GOLDEN_QUERIES_CLAUSE = "Golden Queries 回归与漂移报告（最小集）。"`
    - `FETCHDATA_IMPL_GOLDEN_QUERIES_MIN_SET_RULE = "golden_query_minimal_set_non_empty"`
    - `GOLDEN_QUERY_MIN_SET_MIN_QUERIES = 1`
  - Hardened drift summary validation:
    - Reject empty `query_hashes` (minimal-set enforcement).
    - Reject `total_queries` mismatch against normalized hash entries.
  - Extended drift report payload with requirement metadata (`requirement_id`, `source_document`, `clause`) and minimal-set rule fields.
- Updated `tests/test_qa_fetch_runtime.py`:
  - Added `test_runtime_golden_queries_anchor_matches_qf_033_clause`.
  - Added drift report assertions for `QF-033` metadata fields.
  - Added regression tests for empty minimal-set rejection and `total_queries` mismatch rejection.
- Updated `docs/12_workflows/skeleton_ssot_v1.yaml`:
  - Added execution note under goal `G283` to capture this runtime hardening pass.

## Acceptance Record
- `python3 scripts/check_docs_tree.py`
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py`
- `rg -n "G283|QF-033" docs/12_workflows/skeleton_ssot_v1.yaml`
