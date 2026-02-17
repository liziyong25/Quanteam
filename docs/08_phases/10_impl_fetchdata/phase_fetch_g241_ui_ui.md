# Phase G241: Requirement Gap Closure (QF-012)

## Goal
- Close requirement gap `QF-012` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:24`.

## Requirements
- Requirement ID: QF-012
- Owner Track: impl_fetchdata
- Clause: UI 的交互实现（但必须规定 UI 可审阅的证据接口与产物）。

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
### 1) Runtime QF-012 anchor + UI evidence contract
- Bind runtime to requirement anchor `QF-012` with deterministic constants:
  - requirement id,
  - source document,
  - clause text `UI 的交互实现（但必须规定 UI 可审阅的证据接口与产物）。`.
- Keep `qa_fetch` runtime focused on data execution only, and formalize UI-reviewable
  evidence contract:
  - required UI output interface fields,
  - required evidence artifact path keys.
- Enforce the required artifact keys during `execute_ui_llm_query(...)`.

### 2) Regression test coverage
- Extend `tests/test_qa_fetch_runtime.py` with:
  - a dedicated QF-012 anchor assertion test,
  - UI evidence interface/artifact contract assertions,
  - runtime rejection test when UI-required evidence artifact keys are missing.

### 3) SSOT writeback
- Update `docs/12_workflows/skeleton_ssot_v1.yaml`:
  - goal `G241` status `planned -> implemented`,
  - requirement `QF-012` status `planned -> implemented`,
  - capability cluster `CL_FETCH_241` status `partial -> implemented`.

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
- `rg -n "G241|QF-012" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
