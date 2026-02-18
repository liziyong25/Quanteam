# Phase G372: Requirement Gap Closure (WB-045)

## Goal
- Close requirement gap `WB-045` from `docs/00_overview/workbench_ui_productization_v1.md:114`.
- Freeze and implement a deterministic Phase-0~4 user-result-card matrix for `/ui/workbench`.
- Gate on `G370` (`WB-044`) persistence stability before enabling `WB-045` card writeback behavior.

## Requirements
- Requirement IDs: WB-045
- Owner Track: impl_workbench
- Clause[WB-045]: 用户导向实时策略工作台 UI 改造方案（主控 + Subagent 执行版） / 5. Phase 对应的用户结果卡定义
- Step mapping freeze:
  - `idea` -> `Phase-0`
  - `strategy_spec` -> `Phase-1`
  - `trace_preview` -> `Phase-2`
  - `runspec` -> `Phase-3`
  - `improvements` -> `Phase-4`

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.
- Bundling criterion: same owner track + same source document + same parent requirement + near-adjacent source lines.
- Workbench card builder emits deterministic `phase_label`, `title`, `summary_lines`, and `evidence.result_card_definition`.
- Evidence path handling remains guarded by safe-path resolution (no traversal expansion).

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.
- `/ui/workbench/{session_id}` renders phase-scoped cards in fixed Phase-0~4 order.

## Implementation Plan
TBD by controller at execution time.
