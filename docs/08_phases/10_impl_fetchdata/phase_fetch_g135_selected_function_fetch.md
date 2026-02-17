# Phase G135: Requirement Gap Closure (QF-053)

## Goal
- Close requirement gap `QF-053` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:98`.

## Requirements
- Requirement ID: QF-053
- Owner Track: impl_fetchdata
- Clause: selected_function（最终执行的 fetch_*）

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
1. Runtime write-path hardening:
   - Updated `src/quant_eam/qa_fetch/runtime.py` so `fetch_result_meta.selected_function`
     resolves deterministically from execution result and request payload fallback when
     `resolved_function` is missing.
2. Regression coverage:
   - Added `tests/test_qa_fetch_runtime.py::test_write_fetch_evidence_selected_function_falls_back_to_public_function`
     to lock behavior for blocked/not-in-baseline flows.
3. SSOT writeback:
   - Updated `docs/12_workflows/skeleton_ssot_v1.yaml` to mark `G135`, `QF-053`,
     `CL_FETCH_135`, and linked interface contracts as implemented.

## Acceptance Record
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py` passed (`66 passed`).
