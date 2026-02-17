# Phase G247: Requirement Gap Closure (QF-015)

## Goal
- Close requirement gap `QF-015` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:31`.

## Requirements
- Requirement ID: QF-015
- Owner Track: impl_fetchdata
- Clause: 函数注册表：`docs/05_data_plane/qa_fetch_function_registry_v1.json`

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
### 1) Runtime QF-015 function-registry anchor
- Bind runtime to requirement anchor `QF-015` with deterministic constants:
  - requirement id,
  - source document,
  - clause text `函数注册表：\`docs/05_data_plane/qa_fetch_function_registry_v1.json\``.
- Add an explicit runtime function-registry contract path constant:
  - `docs/05_data_plane/qa_fetch_function_registry_v1.json`.

### 2) Regression test coverage
- Extend `tests/test_qa_fetch_runtime.py` with a dedicated `QF-015` anchor assertion test that verifies:
  - runtime anchor constants (`id/source/clause`),
  - default registry path equals contract path.

### 3) SSOT writeback
- Update `docs/12_workflows/skeleton_ssot_v1.yaml`:
  - goal `G247` status `planned -> implemented`,
  - requirement `QF-015` status `planned -> implemented`,
  - capability cluster `CL_FETCH_247` status `partial -> implemented`.

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
- `rg -n "G247|QF-015" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
