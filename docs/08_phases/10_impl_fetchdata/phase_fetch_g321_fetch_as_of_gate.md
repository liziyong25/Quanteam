# Phase G321: Requirement Gap Closure (QF-079)

## Goal
- Close requirement gap `QF-079` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:147`.

## Requirements
- Requirement IDs: QF-079
- Owner Track: impl_fetchdata
- Clause[QF-079]: fetch 证据必须记录 as_of 与可得性相关摘要（用于复盘与 gate 解释）。

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
- Confirmed `G319` and `G320` are already present as `implemented` in `docs/12_workflows/skeleton_ssot_v1.yaml`, and reused their runtime interfaces for request `as_of` extraction + `available_at<=as_of` guard behavior.
- Implemented `QF-079` evidence closure in `src/quant_eam/qa_fetch/runtime.py`:
  - Added explicit `QF-079` requirement anchors/constants for fetch evidence fields.
  - Emitted `as_of` in stable UTC format (`YYYY-MM-DDTHH:MM:SSZ`) when parseable.
  - Kept `availability_summary` deterministic and aligned with `as_of` normalization.
- Extended runtime coverage in `tests/test_qa_fetch_runtime.py`:
  - Added `QF-079` anchor assertions.
  - Added execution-path assertions verifying persisted `fetch_result_meta.json` includes both `as_of` and `availability_summary`.
  - Updated existing evidence assertions to normalized UTC expectations.
- Updated `docs/12_workflows/skeleton_ssot_v1.yaml` for `G321` and `QF-079` traceability:
  - Added implemented goal block for `G321`.
  - Marked `QF-079` as implemented and mapped to `G321`.
  - Added `CL_FETCH_321` and removed `QF-079` from `CL_LEGACY_CORE`.

## Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py` passed (`260 passed`).
- `rg -n "G321|QF-079" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
