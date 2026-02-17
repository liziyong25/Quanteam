# Phase G263: Requirement Gap Closure (QF-023)

## Goal
- Close requirement gap `QF-023` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:41`.

## Requirements
- Requirement ID: QF-023
- Owner Track: impl_fetchdata
- Clause: 结论：基线函数均可调用（按当前 smoke 口径），无 runtime 阻塞。

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
- Runtime:
  - Add explicit `QF-023` smoke-callable/no-runtime-blockage anchors in `src/quant_eam/qa_fetch/runtime.py`.
  - Bind baseline callable coverage and runtime-blockage checks to dedicated constants:
    `pass_has_data_or_empty=71`, `blocked_source_missing=0`, `error_runtime=0`.
- Tests:
  - Extend `tests/test_qa_fetch_runtime.py` with a dedicated `QF-023` anchor assertion for the smoke callable/no-blockage clause.
- SSOT writeback:
  - Mark `G263`, `QF-023`, and `CL_FETCH_263` as implemented in `docs/12_workflows/skeleton_ssot_v1.yaml`.
