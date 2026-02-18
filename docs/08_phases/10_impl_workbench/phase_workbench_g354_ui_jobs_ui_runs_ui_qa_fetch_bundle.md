# Phase G354: Requirement Gap Closure (WB-007/WB-008/WB-009)

## Goal
- Close requirement gap bundle `WB-007/WB-008/WB-009` from `docs/00_overview/workbench_ui_productization_v1.md:23`.

## Requirements
- Requirement IDs: WB-007/WB-008/WB-009
- Owner Track: impl_workbench
- Clause[WB-007]: 不删除现有 /ui/jobs、/ui/runs、/ui/qa-fetch 等审阅页面。
- Clause[WB-008]: 不绕过 contracts/policies/gates 的治理规则。
- Clause[WB-009]: 不将 Agent 变成最终裁决者（裁决仍由 deterministic kernel + gates 完成）。

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.
- Bundling criterion: same owner track + same source document + same parent requirement + near-adjacent source lines.

## Requirement touchpoint map
- WB-007: `/ui/jobs`, `/ui/runs/<run_id>`、`/ui/qa-fetch` 审阅页面与主入口/跳转链路保持原路由、原模板、原事件流。
- WB-008: 工作台动作通过现有 deterministic 守门链路（`create_job_from_ideaspec`、`advance_job_once`、`run_agent`、GateRunner）进行状态机驱动。
- WB-009: Agent 仅返回可读草稿与建议参数，不写入终态判定；最终裁决必须由 workflow 状态、gates 与 deterministic kernel 决定。

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
1. 审核前置与约束
   - 确认 `G352` 在 `docs/12_workflows/skeleton_ssot_v1.yaml` 为 `implemented`。
   - 已审计并确认：`docs/12_workflows/skeleton_ssot_v1.yaml` 中 `G352` 显示 `status_now: implemented`，并且作为 `G354` 的直接依赖（`depends_on: [G352]`）存在。
   - 复核 `docs/00_overview/workbench_ui_productization_v1.md` 22~25 条与本目标覆盖范围一致。
   - 明确仅落 WB-007/WB-008/WB-009，不触发 WB-010 及后续 FR。
2. 路由与页面留存审计（WB-007）
   - 保持 `/ui/jobs`、`/ui/runs/<run_id>`、`/ui/qa-fetch` 三条审阅链路完整。
   - 检查 `src/quant_eam/api/ui_routes.py` 与模板/入口链接，确认无重定向改写或路由下线。
   - 复核 `tests/test_ui_mvp.py` 对三类 review 页面与事件回放的回归用例。
3. 治理与裁决边界验证（WB-008/WB-009）
   - 追踪 workbench session create/continue/fetch-probe 到现有核方法，不新增 `contracts/policies` 与 `gates` 的旁路。
   - 记录“agent 仅产出辅助信号而非最终结论”的执行边界。
   - 将上述审计与风险记录写入 SSOT notes。
4. SSOT 写回
   - 在 `docs/12_workflows/skeleton_ssot_v1.yaml` 新增 `G354`，并映射 `WB-007/WB-008/WB-009`。
   - 将 `WB-007/WB-008/WB-009` 状态改为 `implemented`。
   - 执行验收命令：
     - `python3 scripts/check_docs_tree.py`
     - `python3 -m pytest -q tests/test_ui_mvp.py`
     - `rg -n "G354|WB-007|WB-008|WB-009" docs/12_workflows/skeleton_ssot_v1.yaml`

## Route integrity and governance checks
- 在 phase 交付期间不修改 `contracts/**`、`policies/**`、`Holdout visibility expansion`。
- 不对 `/ui/jobs`、`/ui/runs`、`/ui/qa-fetch` 路由进行清理、迁移或重写。
- 不引入“Agent 直接返回 PASS/FAIL 并终结任务”的行为；任何终态仅由 orchestrator step + gates + policy 判定触发。

## Required skills
- requirement-splitter
- ssot-goal-planner
- phase-authoring
- packet-evidence-guard
