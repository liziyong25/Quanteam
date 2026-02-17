# Phase G227: Requirement Gap Closure (QF-005)

## Goal
- Close requirement gap `QF-005` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:15`.

## Requirements
- Requirement ID: QF-005
- Owner Track: impl_fetchdata
- Clause: 接受来自主链路的 `fetch_request`（intent 优先）；

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
### 1) Runtime anchor closure for QF-005 clause
- Add deterministic runtime constants that bind implementation to:
  - requirement id `QF-005`,
  - source document `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md`,
  - clause `接受来自主链路的 fetch_request（intent 优先）`.

### 2) Regression test coverage for QF-005
- Extend `tests/test_qa_fetch_runtime.py` with:
  - an anchor test asserting the `QF-005` runtime constants,
  - an intent-priority behavior test asserting nested `intent` fields override
    conflicting top-level wrapper fields.

### 3) SSOT writeback
- Update `docs/12_workflows/skeleton_ssot_v1.yaml`:
  - goal `G227` status to `implemented`,
  - requirement `QF-005` status to `implemented`,
  - capability cluster `CL_FETCH_227` status to `implemented`.

## Execution Record
- Date: 2026-02-14.
- Implemented runtime anchor constants in:
  - `src/quant_eam/qa_fetch/runtime.py`
- Added regression anchor + intent-priority tests in:
  - `tests/test_qa_fetch_runtime.py`
- Updated SSOT linkage/status in:
  - `docs/12_workflows/skeleton_ssot_v1.yaml`

## Acceptance Record
- `python3 scripts/check_docs_tree.py`
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py`
- `rg -n "G227|QF-005" docs/12_workflows/skeleton_ssot_v1.yaml`
