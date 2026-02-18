# Phase G357: Requirement Gap Closure (WB-011/WB-012/WB-013/WB-014/WB-020)

## Goal
- Close requirement gap bundle `WB-011/WB-012/WB-013/WB-014/WB-020` from `docs/00_overview/workbench_ui_productization_v1.md:61`.

## Requirements
- Requirement IDs: WB-011/WB-012/WB-013/WB-014/WB-020
- Owner Track: impl_workbench
- Clause[WB-011]: FR-001 工作台会话创建: 用户输入 Idea 约束后创建会话与关联 job。
- Clause[WB-012]: FR-002 一键推进: 在每个检查点可点击“继续”，系统自动审批并推进到下一检查点或终态。
- Clause[WB-013]: FR-003 取数即时反馈: 用户在 Phase‑0 即可触发 fetch 预览并看到表格样本。
- Clause[WB-014]: FR-004 逻辑可读输出: Strategy 阶段展示 pseudocode、变量字典摘要、trace plan 摘要。
- Clause[WB-020]: FR-010 全程审计: 用户动作与系统动作都写会话事件日志。

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
Contract freeze from G356 is reused and the following execution work is implemented:
- Keep session/job/event payload schema versions stable while adding explicit audit entries for all user/system actions in WB-011/012/013/014/020 paths.
- Wire Idea intake into real job creation so `/workbench/sessions` creates and binds a job artifact under `artifacts/jobs/<job_id>/`.
- Implement checkpoint-driven continue that auto-approves waiting checkpoints and advances through workbench phases/terminal state.
- Surface Phase-0 fetch preview evidence in the session page with explicit success/error/loading status and sample table rendering.
- Provide strategy readable summary (`pseudocode`, `variable_dictionary`, `trace_plan`) from job outputs and expose it in result cards.
