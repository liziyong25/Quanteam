# Phase G231: Requirement Gap Closure (QF-007)

## Goal
- Close requirement gap `QF-007` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:17`.

## Requirements
- Requirement ID: QF-007
- Owner Track: impl_fetchdata
- Clause: 为每次取数强制落盘证据；

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
### 1) Runtime QF-007 enforcement
- Bind runtime to requirement anchor `QF-007` with deterministic constants:
  - requirement id,
  - source document,
  - clause text `为每次取数强制落盘证据；`.
- Enforce evidence write at public runtime entrypoints:
  - `execute_fetch_by_name(...)`
  - `execute_fetch_by_intent(...)`
- Keep internal opt-out only for nested runtime orchestration calls to avoid duplicate
  evidence bundles inside a single top-level execution.

### 2) Regression test coverage
- Extend `tests/test_qa_fetch_runtime.py` with:
  - QF-007 anchor assertion test,
  - explicit tests proving `write_evidence=False` is ignored at public entrypoints
    (runtime evidence still persists).

### 3) SSOT writeback
- Update `docs/12_workflows/skeleton_ssot_v1.yaml`:
  - goal `G231` status `planned -> implemented`,
  - requirement `QF-007` status `planned -> implemented`,
  - capability cluster `CL_FETCH_231` status `partial -> implemented`.

## Execution Record
- Date: 2026-02-14
- Runtime changes:
  - `src/quant_eam/qa_fetch/runtime.py`
- Test changes:
  - `tests/test_qa_fetch_runtime.py`
- SSOT changes:
  - `docs/12_workflows/skeleton_ssot_v1.yaml`

## Acceptance Record
- `python3 scripts/check_docs_tree.py`
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py`
- `rg -n "G231|QF-007" docs/12_workflows/skeleton_ssot_v1.yaml`
