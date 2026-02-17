# Phase G233: Requirement Gap Closure (QF-008)

## Goal
- Close requirement gap `QF-008` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:18`.

## Requirements
- Requirement ID: QF-008
- Owner Track: impl_fetchdata
- Clause: 为 DataCatalog/time‑travel 与 gates 提供可审计输入基础；

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
### 1) Runtime QF-008 traceability anchor
- Bind runtime to requirement anchor `QF-008` with deterministic constants:
  - requirement id,
  - source document,
  - clause text `为 DataCatalog/time‑travel 与 gates 提供可审计输入基础；`.
- Keep behavior deterministic and reuse existing audited meta fields already emitted for
  time-travel/gate inputs (`as_of`, `availability_summary`, `gate_input_summary`).

### 2) Regression test coverage
- Extend `tests/test_qa_fetch_runtime.py` with:
  - QF-008 anchor assertion test that verifies requirement id, source document, and clause text.

### 3) SSOT writeback
- Update `docs/12_workflows/skeleton_ssot_v1.yaml`:
  - goal `G233` status `planned -> implemented`,
  - requirement `QF-008` status `planned -> implemented`,
  - capability cluster `CL_FETCH_233` status `partial -> implemented`.

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
- `rg -n "G233|QF-008" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
