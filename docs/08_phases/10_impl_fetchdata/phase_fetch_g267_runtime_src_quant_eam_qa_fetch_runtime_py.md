# Phase G267: Requirement Gap Closure (QF-025)

## Goal
- Close requirement gap `QF-025` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:44`.

## Requirements
- Requirement ID: QF-025
- Owner Track: impl_fetchdata
- Clause: runtime：`src/quant_eam/qa_fetch/runtime.py`

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
1. Add explicit QF-025 runtime-module anchors in `src/quant_eam/qa_fetch/runtime.py`:
   - `FETCHDATA_IMPL_RUNTIME_MODULE_REQUIREMENT_ID`
   - `FETCHDATA_IMPL_RUNTIME_MODULE_SOURCE_DOCUMENT`
   - `FETCHDATA_IMPL_RUNTIME_MODULE_CLAUSE`
   - keep `RUNTIME_MODULE_CONTRACT_PATH` bound to `src/quant_eam/qa_fetch/runtime.py`.
2. Extend `tests/test_qa_fetch_runtime.py` to assert the new QF-025 anchors and
   module-path binding.
3. Write back SSOT state in `docs/12_workflows/skeleton_ssot_v1.yaml` so `G267`,
   `QF-025`, and `CL_FETCH_267` transition to implemented.
