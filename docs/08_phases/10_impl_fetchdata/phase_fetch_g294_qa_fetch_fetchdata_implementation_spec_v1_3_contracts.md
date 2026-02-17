# Phase G294: Requirement Gap Closure (QF-038)

## Goal
- Close requirement gap `QF-038` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:76`.

## Requirements
- Requirement IDs: QF-038
- Owner Track: impl_fetchdata
- Clause[QF-038]: QA‑Fetch FetchData Implementation Spec (v1) / 3. 对外接口与 Contracts（Interfaces） / 3.1 FetchRequest v1（intent-first）
- Extracted FetchRequest v1 contract:
  - intent-first expression by default (`intent` over direct function dispatch)
  - minimum request shape includes `mode`, `intent`, and `policy`
  - `intent` includes `asset`, `freq`, `venue|universe`, `adjust`, optional `symbols`, `start`, `end`, optional `fields`, optional `auto_symbols`, optional `sample`
  - `policy` includes `on_no_data` with optional `max_symbols`/`max_rows`/`retry_strategy`
  - pre-orchestrator schema+logic validation is fail-fast
  - `intent` and `function` paths are mutually exclusive; function mode is strong-control only

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.
- Dependency lock: G292 (`QF-037`) must be implemented before enabling `QF-038` writeback.
- Bundling criterion: same owner track + same source document + same parent requirement + near-adjacent source lines.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
TBD by controller at execution time.
