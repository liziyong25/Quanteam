# Phase G93: Requirement Gap Closure (QF-010)

## Goal
- Close requirement gap `QF-010` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:22`.

## Requirements
- Requirement ID: QF-010
- Owner Track: impl_fetchdata
- Clause: 策略逻辑生成、回测引擎实现（属于 Backtest Plane / Kernel）；

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
### Execution Strategy
- Keep valid fetch request execution behavior unchanged.
- Add a deterministic runtime guard that blocks Backtest Plane / Kernel payload fields from entering `qa_fetch` execution.
- Lock the boundary with focused runtime tests and SSOT requirement writeback.

### Concrete Changes
- Added boundary contract documentation:
  - `docs/05_data_plane/qa_fetch_backtest_plane_kernel_boundary_contract_v1.md`
- Updated runtime boundary enforcement:
  - `src/quant_eam/qa_fetch/runtime.py`
  - Added guard for forbidden backtest/kernel fields in:
    - `fetch_request`
    - `fetch_request.intent`
    - `fetch_request.kwargs`
    - `intent.extra_kwargs`
- Added runtime regression tests:
  - `tests/test_qa_fetch_runtime.py`
  - Added assertions that forbidden backtest/kernel fields raise `ValueError`.
- Updated SSOT status writeback:
  - `docs/12_workflows/skeleton_ssot_v1.yaml`
  - `G93` and `QF-010` marked implemented.
  - Interface contracts linked to `impl_requirement_id: QF-010` marked implemented.

### Acceptance Record
- `python3 scripts/check_docs_tree.py`
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py`
- `rg -n "G93|QF-010" docs/12_workflows/skeleton_ssot_v1.yaml`
