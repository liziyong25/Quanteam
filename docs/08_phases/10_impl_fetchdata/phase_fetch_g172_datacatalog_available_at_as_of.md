# Phase G172: Requirement Gap Closure (QF-084)

## Goal
- Close requirement gap `QF-084` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:146`.

## Requirements
- Requirement ID: QF-084
- Owner Track: impl_fetchdata
- Clause: DataCatalog 层必须强制 `available_at <= as_of`；

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
- Runtime enforcement hardening:
  - `src/quant_eam/qa_fetch/runtime.py` keeps `available_at <= as_of` filtering active when `as_of` is provided, and treats missing/invalid `available_at` as non-compliant rows when the field is present.
  - Preserve legacy bypass behavior when `available_at` is entirely absent from payload rows (no field to enforce).
- Regression coverage:
  - `tests/test_qa_fetch_runtime.py` verifies strict row filtering for missing/invalid/future `available_at` values and verifies passthrough when payload rows do not include `available_at`.
- SSOT traceability:
  - `docs/12_workflows/skeleton_ssot_v1.yaml` must contain `G172` and linked requirement `QF-084` entries for acceptance grep/writeback flow.
