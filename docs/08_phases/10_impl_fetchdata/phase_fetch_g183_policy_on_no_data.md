# Phase G183: Requirement Gap Closure (QF-091)

## Goal
- Close requirement gap `QF-091` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:158`.

## Requirements
- Requirement ID: QF-091
- Owner Track: impl_fetchdata
- Clause: 空数据语义与 policy.on_no_data 一致

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
### 1) Runtime semantic enforcement
- Add explicit runtime clause anchor for QF-091:
  - `SANITY_EMPTY_DATA_POLICY_RULE = "empty_data_semantics_consistent_with_policy_on_no_data"`.
- Extend fetch evidence `sanity_checks` metadata to record no-data policy semantics:
  - `on_no_data_policy`
  - `empty_data_expected_status`
  - `empty_data_observed_status`
  - `empty_data_semantics_consistent`
- Keep execution behavior deterministic and unchanged for non-empty data paths.

### 2) Regression coverage
- Add anchor test for QF-091 runtime constant.
- Add no-data exception path tests to confirm policy behavior:
  - `on_no_data=error` => terminal `error_runtime`.
  - `on_no_data=retry` => retries no-data exception and succeeds on later data.
- Extend evidence meta tests to assert `sanity_checks` no-data policy consistency fields.

### 3) Contracts and SSOT writeback
- Update `docs/05_data_plane/qa_fetch_sanity_checks_contract_v1.md` with new no-data policy consistency fields.
- Mark SSOT entries implemented:
  - Goal `G183`
  - Requirement `QF-091`
  - Capability cluster `CL_FETCH_183`
  - Interfaces `IFC-QF_034-QF_091` and `IFC-QF_089-QF_091`

## Execution Record
- Date: 2026-02-14.
- Scope outcome:
  - QF-091 is explicitly anchored in runtime metadata contracts.
  - Fetch evidence now records whether terminal no-data outcome is consistent with `policy.on_no_data`.
  - Runtime regression tests cover no-data exception semantics for `error` and `retry`.
  - SSOT writeback marks G183/QF-091 and linked interface contracts as implemented.

## Acceptance Record
- `python3 scripts/check_docs_tree.py`
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py`
- `rg -n "G183|QF-091" docs/12_workflows/skeleton_ssot_v1.yaml`
