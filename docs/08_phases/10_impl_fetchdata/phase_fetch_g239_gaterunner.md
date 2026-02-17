# Phase G239: Requirement Gap Closure (QF-011)

## Goal
- Close requirement gap `QF-011` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:23`.

## Requirements
- Requirement ID: QF-011
- Owner Track: impl_fetchdata
- Clause: 策略是否有效的裁决（只允许 GateRunner 裁决）；

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
### 1) Runtime QF-011 boundary anchor
- Bind runtime to requirement anchor `QF-011` with deterministic constants:
  - requirement id,
  - source document,
  - clause text `策略是否有效的裁决（只允许 GateRunner 裁决）；`.
- Keep `qa_fetch` runtime scoped to data fetch execution and reject GateRunner-only
  arbitration payload fields.

### 2) Regression test coverage
- Extend `tests/test_qa_fetch_runtime.py` with:
  - a dedicated QF-011 anchor assertion test,
  - explicit rejection tests for GateRunner-only arbitration fields in:
    - `fetch_request.intent`,
    - `intent.extra_kwargs`.
- Preserve existing rejection coverage for `fetch_request` and `fetch_request.kwargs`.

### 3) SSOT writeback
- Update `docs/12_workflows/skeleton_ssot_v1.yaml`:
  - goal `G239` status `planned -> implemented`,
  - requirement `QF-011` status `planned -> implemented`,
  - capability cluster `CL_FETCH_239` status `partial -> implemented`.

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
- `rg -n "G239|QF-011" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
