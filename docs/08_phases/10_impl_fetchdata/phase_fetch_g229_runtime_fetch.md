# Phase G229: Requirement Gap Closure (QF-006)

## Goal
- Close requirement gap `QF-006` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:16`.

## Requirements
- Requirement ID: QF-006
- Owner Track: impl_fetchdata
- Clause: 通过统一 runtime 解析/执行 fetch；

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
### 1) Runtime anchor closure for QF-006 clause
- Add deterministic runtime constants that bind implementation to:
  - requirement id `QF-006`,
  - source document `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md`,
  - clause `通过统一 runtime 解析/执行 fetch；`.

### 2) Regression test coverage for QF-006
- Extend `tests/test_qa_fetch_runtime.py` with:
  - an anchor test asserting the `QF-006` runtime constants,
  - entrypoint linkage assertions proving both intent/name execution paths are runtime-owned.

### 3) SSOT writeback
- Update `docs/12_workflows/skeleton_ssot_v1.yaml`:
  - goal `G229` status to `implemented`,
  - requirement `QF-006` status to `implemented`,
  - capability cluster `CL_FETCH_229` status to `implemented`.

## Execution Record
- Date: 2026-02-14.
- Implemented runtime anchor constants in:
  - `src/quant_eam/qa_fetch/runtime.py`
- Added regression anchor assertions in:
  - `tests/test_qa_fetch_runtime.py`
- Updated SSOT linkage/status in:
  - `docs/12_workflows/skeleton_ssot_v1.yaml`

## Acceptance Record
- `python3 scripts/check_docs_tree.py`
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py`
- `rg -n "G229|QF-006" docs/12_workflows/skeleton_ssot_v1.yaml`
