# Phase G170: Requirement Gap Closure (QF-081)

## Goal
- Close requirement gap `QF-081` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:140`.

## Requirements
- Requirement ID: QF-081
- Owner Track: impl_fetchdata
- Clause: adjust 默认 raw（用户明确才切换复权口径）

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
- Add an explicit runtime anchor for `QF-081` default adjust semantics:
  - `TECHNICAL_INDICATOR_DEFAULT_ADJUST = "raw"` in `src/quant_eam/qa_fetch/runtime.py`.
- Normalize `intent.adjust` consistently in `_coerce_intent(...)`:
  - Missing/blank/non-explicit adjust resolves to `raw`.
  - Explicit adjust values remain user-controlled and pass through to resolver dispatch.
- Add focused runtime tests in `tests/test_qa_fetch_runtime.py`:
  - QF-081 anchor assertion.
  - `FetchIntent(adjust=None)` normalization to default `raw`.
  - Explicit adjust override (`qfq`) is preserved.
- Write SSOT status updates for `G170` / `QF-081` after acceptance checks pass.
