# Phase G237: Requirement Gap Closure (QF-010)

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
### 1) Runtime QF-010 boundary anchor
- Bind runtime to requirement anchor `QF-010` with deterministic constants:
  - requirement id,
  - source document,
  - clause text `策略逻辑生成、回测引擎实现（属于 Backtest Plane / Kernel）；`.
- Keep `qa_fetch` runtime scoped as Data Plane fetch execution only.

### 2) Regression test coverage
- Extend `tests/test_qa_fetch_runtime.py` with:
  - a dedicated QF-010 anchor assertion test,
  - explicit rejection tests for Backtest Plane fields in:
    - `fetch_request.intent`,
    - `intent.extra_kwargs`.
- Preserve existing rejection coverage for `fetch_request` and `fetch_request.kwargs`.

### 3) SSOT writeback
- Update `docs/12_workflows/skeleton_ssot_v1.yaml`:
  - goal `G237` status `planned -> implemented`,
  - requirement `QF-010` status `planned -> implemented`,
  - capability cluster `CL_FETCH_237` status `partial -> implemented`.

## Execution Record
- Date: 2026-02-14
- Runtime changes:
  - `src/quant_eam/qa_fetch/runtime.py`
- Test changes:
  - `tests/test_qa_fetch_runtime.py`
- SSOT changes:
  - `docs/12_workflows/skeleton_ssot_v1.yaml`

## Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py` passed.
- `rg -n "G237|QF-010" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
