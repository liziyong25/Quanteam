# Phase G115: Requirement Gap Closure (QF-032)

## Goal
- Close requirement gap `QF-032` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:60`.

## Requirements
- Requirement ID: QF-032
- Owner Track: impl_fetchdata
- Clause: time‑travel 可得性（`available_at <= as_of`）；

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
  - `src/quant_eam/qa_fetch/runtime.py` adds `TIME_TRAVEL_AVAILABILITY_RULE = "available_at<=as_of"` as the explicit QF-032 clause anchor and reuses it in availability/gate metadata emission paths.
- Test coverage:
  - `tests/test_qa_fetch_runtime.py` adds `test_runtime_time_travel_rule_anchor_matches_qf_032_clause` and aligns existing no-lookahead rule assertions to the shared runtime anchor.
- SSOT writeback:
  - `docs/12_workflows/skeleton_ssot_v1.yaml` marks `G115`, `QF-032`, `CL_FETCH_115`, and all linked `interface_contracts_v1` rows for `impl_requirement_id: QF-032` as implemented.
