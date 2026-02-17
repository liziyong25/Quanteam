# Phase G319: Requirement Gap Closure (QF-077)

## Goal
- Close requirement gap `QF-077` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:145`.

## Requirements
- Requirement IDs: QF-077
- Owner Track: impl_fetchdata
- Clause[QF-077]: QA‑Fetch FetchData Implementation Spec (v1) / 6. 正确性保障（Correctness） / 6.1 time-travel 可得性

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
- Confirmed `G318` is present in `docs/12_workflows/skeleton_ssot_v1.yaml` with `status_now: implemented` before starting `G319`.
- Impl-fetch interface assumptions for `QF-077` execution:
  - `as_of` is extracted from request payload (`top-level`, `intent`, then `kwargs`).
  - Time-travel eligibility is enforced by `available_at <= as_of` when `available_at` is present.
  - Historical unavailability is treated as a dedicated runtime outcome (`time_travel_unavailable`) to enable adaptive fallback and deterministic terminal error handling.

## Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py` passed.
- `rg -n "G319|QF-077" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
