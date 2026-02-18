# Phase G352: Requirement Gap Closure (WB-006)

## Goal
- Close requirement gap `WB-006` from `docs/00_overview/workbench_ui_productization_v1.md:22`.

## Requirements
- Requirement IDs: WB-006
- Owner Track: impl_workbench
- Clause[WB-006]: 用户导向实时策略工作台 UI 改造方案（主控 + Subagent 执行版） / 2.2 非目标

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
- Scope lock: this phase only closes parent requirement `WB-006` (section `2.2 非目标` summary) and does not implement child non-goal clauses.
- Dependency gate: confirm `G350` is `implemented` in `docs/12_workflows/skeleton_ssot_v1.yaml` before any `G352` writeback.
- SSOT goal writeback: add `G352` goal metadata (`depends_on=G350`, `track=impl_workbench`, `requirement_ids=[WB-006]`, scoped `allowed_paths`, acceptance commands, stop-condition scope).
- Requirement trace writeback: update only `requirements_trace_v1/WB-006` to `implemented` with `mapped_goal_ids=[G352]` and acceptance commands.
- Non-target guard: keep `WB-007/WB-008/WB-009` as `planned` with `depends_on_req_ids=[WB-006]` unchanged.
- Validation and evidence: run acceptance commands and retain execution evidence under `artifacts/subagent_control/G352/**`.
- TBD by controller at execution time.
