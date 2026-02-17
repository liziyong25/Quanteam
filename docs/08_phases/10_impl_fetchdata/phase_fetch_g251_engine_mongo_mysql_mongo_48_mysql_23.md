# Phase G251: Requirement Gap Closure (QF-017)

## Goal
- Close requirement gap `QF-017` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:33`.

## Requirements
- Requirement ID: QF-017
- Owner Track: impl_fetchdata
- Clause: 引擎拆分：`engine=mongo|mysql`（分布：mongo 48、mysql 23）

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
### 1) Runtime QF-017 engine-split anchor
- Bind runtime to requirement anchor `QF-017` with deterministic constants:
  - requirement id,
  - source document,
  - clause text `引擎拆分：\`engine=mongo|mysql\`（分布：mongo 48、mysql 23）`.

### 2) Runtime contract linkage verification
- Reuse existing runtime baseline engine contract implementation:
  - baseline split `BASELINE_ENGINE_SPLIT={"mongo": 48, "mysql": 23}`,
  - registry split enforcement in `load_function_registry(...)`.

### 3) Regression test coverage
- Extend `tests/test_qa_fetch_runtime.py` with a dedicated `QF-017` anchor assertion test that verifies:
  - runtime anchor constants (`id/source/clause`),
  - baseline split and engine-to-internal-source mapping constants.

### 4) SSOT writeback
- Update `docs/12_workflows/skeleton_ssot_v1.yaml`:
  - goal `G251` status `planned -> implemented`,
  - requirement `QF-017` status `planned -> implemented`,
  - capability cluster `CL_FETCH_251` status `partial -> implemented`.

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
- `rg -n "G251|QF-017" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
