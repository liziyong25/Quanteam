# Phase G245: Requirement Gap Closure (QF-014)

## Goal
- Close requirement gap `QF-014` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:29`.

## Requirements
- Requirement ID: QF-014
- Owner Track: impl_fetchdata
- Clause: QA‑Fetch FetchData Implementation Spec (v1) / 1. 现有事实基线（必须保持可回归） / 1.1 函数基线

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
### 1) Runtime QF-014 function-baseline anchor
- Bind runtime to requirement anchor `QF-014` with deterministic constants:
  - requirement id,
  - source document,
  - clause text `QA‑Fetch FetchData Implementation Spec (v1) / 1. 现有事实基线（必须保持可回归） / 1.1 函数基线`.
- Keep scope at the `1.1 函数基线` clause level and reuse existing deterministic baseline contracts:
  - `BASELINE_FUNCTION_COUNT`,
  - `BASELINE_ENGINE_SPLIT`.

### 2) Regression test coverage
- Extend `tests/test_qa_fetch_runtime.py` with a dedicated `QF-014` anchor assertion test that verifies:
  - runtime anchor constants (`id/source/clause`),
  - function-baseline invariants (`BASELINE_FUNCTION_COUNT` and split-total consistency).

### 3) SSOT writeback
- Update `docs/12_workflows/skeleton_ssot_v1.yaml`:
  - goal `G245` status `planned -> implemented`,
  - requirement `QF-014` status `planned -> implemented`,
  - capability cluster `CL_FETCH_245` status `partial -> implemented`.

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
- `rg -n "G245|QF-014" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
