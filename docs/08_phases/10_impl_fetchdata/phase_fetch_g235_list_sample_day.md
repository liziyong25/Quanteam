# Phase G235: Requirement Gap Closure (QF-009)

## Goal
- Close requirement gap `QF-009` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:19`.

## Requirements
- Requirement ID: QF-009
- Owner Track: impl_fetchdata
- Clause: 支持多步取数（如 list→sample→day）并可追溯。

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
### 1) Runtime QF-009 traceability anchor
- Bind runtime to requirement anchor `QF-009` with deterministic constants:
  - requirement id,
  - source document,
  - clause text `支持多步取数（如 list→sample→day）并可追溯。`.
- Reuse existing runtime planner execution/evidence path that already emits deterministic
  list→sample→day step records and `fetch_steps_index.json`.

### 2) Regression test coverage
- Extend `tests/test_qa_fetch_runtime.py` with a dedicated QF-009 anchor assertion test
  (requirement id, source document, clause text).
- Keep existing planner behavior tests as functional proof of list→sample→day execution
  and traceable step evidence.

### 3) SSOT writeback
- Update `docs/12_workflows/skeleton_ssot_v1.yaml`:
  - goal `G235` status `planned -> implemented`,
  - requirement `QF-009` status `planned -> implemented`,
  - capability cluster `CL_FETCH_235` status `partial -> implemented`.

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
- `rg -n "G235|QF-009" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
