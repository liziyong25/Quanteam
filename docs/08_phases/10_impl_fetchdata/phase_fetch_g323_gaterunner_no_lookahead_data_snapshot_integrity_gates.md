# Phase G323: Requirement Gap Closure (QF-081)

## Goal
- Close requirement gap `QF-081` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:150`.

## Requirements
- Requirement IDs: QF-081
- Owner Track: impl_fetchdata
- Clause[QF-081]: GateRunner 必须包含 no_lookahead 与 data_snapshot_integrity（或等价 gates）；

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
- Verified dependency before implementation:
  - `G322` is `status_now: implemented` in `docs/12_workflows/skeleton_ssot_v1.yaml`.
- Confirmed GateRunner dual-gate runtime contract in `src/quant_eam/qa_fetch/runtime.py`:
  - Added explicit `QF-081` anchors for the dual-gate clause.
  - Kept gate contract deterministic with stable gate names:
    - `no_lookahead`
    - `data_snapshot_integrity`
  - Kept scope limited to `QF-081`; no `QF-082` fail-fast behavior changes.
- Updated `tests/test_qa_fetch_runtime.py`:
  - Added `QF-081` anchor assertions for dual-gate clause/source linkage.
  - Added explicit literal gate-name assertions for stable naming and output key order.
- Updated SSOT mapping in `docs/12_workflows/skeleton_ssot_v1.yaml`:
  - Added implemented goal block `G323`.
  - Marked `QF-081` as implemented and mapped it to `G323`.
  - Added `CL_FETCH_323` and moved `QF-081` linkage out of the legacy pending list.

## Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py` passed.
- `rg -n "G323|QF-081" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
