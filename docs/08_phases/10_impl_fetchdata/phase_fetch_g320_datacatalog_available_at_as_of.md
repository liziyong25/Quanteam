# Phase G320: Requirement Gap Closure (QF-078)

## Goal
- Close requirement gap `QF-078` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:146`.

## Requirements
- Requirement IDs: QF-078
- Owner Track: impl_fetchdata
- Clause[QF-078]: DataCatalog 层必须强制 available_at <= as_of；

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.
- Bundling criterion: same owner track + same source document + same parent requirement + near-adjacent source lines.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
TBD by controller at execution time.

## Execution Record
- Confirmed dependency status before implementation on 2026-02-16:
  - `G319` is marked `status_now: implemented` in `docs/12_workflows/skeleton_ssot_v1.yaml`.
  - Runtime time-travel interface remains stable on `as_of` extraction precedence (`top-level` -> `intent` -> `kwargs`) and `available_at` comparison contract.
- Implemented QF-078 DataCatalog enforcement hardening in fetch runtime:
  - Added explicit QF-078 clause anchors in `src/quant_eam/qa_fetch/runtime.py`.
  - Routed runtime no-lookahead filtering through a dedicated DataCatalog guard (`_apply_datacatalog_available_at_as_of_guard`) that enforces `available_at <= as_of`.
  - Guard behavior remains deterministic:
    - `available_at == as_of` rows are retained.
    - `available_at > as_of` rows are filtered.
    - If all candidate rows violate availability, runtime raises terminal `time_travel_unavailable`.
- Added/updated runtime tests in `tests/test_qa_fetch_runtime.py`:
  - QF-078 anchor contract assertions.
  - Boundary and failure coverage for equal timestamp pass and future timestamp rejection.

## Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py` passed.
- `rg -n "G320|QF-078" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
- `python3 scripts/check_subagent_packet.py --phase-id G320` passed.
