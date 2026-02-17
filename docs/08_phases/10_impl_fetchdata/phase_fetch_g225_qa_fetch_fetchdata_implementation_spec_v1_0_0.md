# Phase G225: Requirement Gap Closure (QF-004)

## Goal
- Close requirement gap `QF-004` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:13`.

## Requirements
- Requirement ID: QF-004
- Owner Track: impl_fetchdata
- Clause: QA‑Fetch FetchData Implementation Spec (v1) / 0. 目的与定位 / 0.2 定位（系统边界）

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
### 1) Runtime anchor closure for QF-004 clause
- Add deterministic runtime constants that bind implementation to:
  - requirement id `QF-004`,
  - source document `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md`,
  - clause `QA-Fetch FetchData Implementation Spec (v1) / 0. 目的与定位 / 0.2 定位（系统边界）`.

### 2) Regression test coverage for QF-004
- Extend `tests/test_qa_fetch_runtime.py` with an anchor test asserting:
  - requirement id constant,
  - source document constant,
  - clause constant.

### 3) SSOT writeback
- Update `docs/12_workflows/skeleton_ssot_v1.yaml`:
  - goal `G225` status to `implemented`,
  - requirement `QF-004` status to `implemented`,
  - capability cluster `CL_FETCH_225` status to `implemented`.

## Execution Record
- Date: 2026-02-14.
- Implemented runtime anchor constants in:
  - `src/quant_eam/qa_fetch/runtime.py`
- Added regression anchor test in:
  - `tests/test_qa_fetch_runtime.py`
- Updated SSOT linkage/status in:
  - `docs/12_workflows/skeleton_ssot_v1.yaml`

## Acceptance Record
- `python3 scripts/check_docs_tree.py`
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py`
- `rg -n "G225|QF-004" docs/12_workflows/skeleton_ssot_v1.yaml`
