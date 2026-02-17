# Phase G107: Requirement Gap Closure (QF-023)

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
- Runtime contract:
  - `src/quant_eam/qa_fetch/runtime.py` extends baseline probe-summary validation for the QF-023 smoke conclusion by enforcing `pass_has_data_or_empty=71` and zero runtime-blocking statuses (`blocked_source_missing=0`, `error_runtime=0`) when baseline totals are loaded.
- Test coverage:
  - `tests/test_qa_fetch_runtime.py` adds deterministic mismatch tests for callable-coverage/runtime-blockage clauses and keeps baseline acceptance assertions explicit.
- SSOT writeback:
  - `docs/12_workflows/skeleton_ssot_v1.yaml` marks `QF-023`, `G107`, `CL_FETCH_107`, and linked QF-023 interface contracts as implemented.
