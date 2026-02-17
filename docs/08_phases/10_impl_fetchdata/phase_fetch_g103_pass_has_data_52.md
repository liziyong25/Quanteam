# Phase G103: Requirement Gap Closure (QF-021)

## Goal
- Close requirement gap `QF-021` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:39`.

## Requirements
- Requirement ID: QF-021
- Owner Track: impl_fetchdata
- Clause: pass_has_data=52

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
  - `src/quant_eam/qa_fetch/runtime.py` adds probe-summary loader/validator that enforces the baseline smoke clause `total=71 => pass_has_data=52` when a baseline summary file is loaded.
- Test coverage:
  - `tests/test_qa_fetch_runtime.py` adds deterministic tests for baseline mismatch rejection and exact baseline acceptance.
- SSOT writeback:
  - `docs/12_workflows/skeleton_ssot_v1.yaml` marks `QF-021` and `G103` as implemented.
