# Phase G297: Requirement Gap Closure (QF-043/QF-044/QF-045/QF-046)

## Goal
- Close requirement gap bundle `QF-043/QF-044/QF-045/QF-046` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:86`.

## Requirements
- Requirement IDs: QF-043/QF-044/QF-045/QF-046
- Owner Track: impl_fetchdata
- Clause[QF-043]: auto_symbols（bool，可选）
- Clause[QF-044]: sample（可选：n/method）
- Clause[QF-045]: on_no_data: error | pass_empty | retry
- Clause[QF-046]: （可选）max_symbols/max_rows/retry_strategy

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.
- Dependency baseline: `G294` is implemented and provides reusable FetchRequest v1 interface/data-contract behavior.
- Bundling criterion: same owner track + same source document + same parent requirement + near-adjacent source lines.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
TBD by controller at execution time.
