# Phase G362: Requirement Gap Closure (WB-033/WB-034/WB-035/WB-036)

## Goal
- Close requirement gap bundle `WB-033/WB-034/WB-035/WB-036` from `docs/00_overview/workbench_ui_productization_v1.md:100`.

## Requirements
- Requirement IDs: WB-033/WB-034/WB-035/WB-036
- Owner Track: impl_workbench
- Clause[WB-033]: GET /workbench/sessions/{session_id}/events（SSE 或轮询兼容）
- Clause[WB-034]: POST /workbench/sessions/{session_id}/fetch-probe
- Clause[WB-035]: POST /workbench/sessions/{session_id}/steps/{step}/drafts
- Clause[WB-036]: POST /workbench/sessions/{session_id}/steps/{step}/drafts/{version}/apply

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
