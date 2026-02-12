# Phase-59: Whole View Workflow Checkpoints Matrix Page (G39)

## 1) 目标（Goal）
- 完成 G39：交付 `/ui/workflow-checkpoints` 只读页面，展示 Whole View section 3 的 workflow phases 与 UI checkpoint 边界证据。

## 2) 背景（Background）
- Whole View section 3 定义了 Idea -> Blueprint -> Demo -> Backtest -> 改进的阶段推进与审阅点。
- 无人值守流程要求将 workflow checkpoint 边界可视化为只读治理证据，降低对源码阅读依赖。

## 3) 范围（Scope）
### In Scope
- 新增 `/ui/workflow-checkpoints` 只读路由和模板渲染。
- 从 Whole View + Playbook 提取 phase/checkpoint 证据并映射到 SSOT orchestration 结构。
- 增补 G39 回归测试覆盖可访问性、只读语义与关键证据字段展示。

### Out of Scope
- 修改 `contracts/**`。
- 修改 `policies/**`。
- 扩展 holdout 可见性。
- 新增写接口或修改非 G39 范围路由行为。

## 4) 任务卡（Task Card）
### Single Deliverable
- `G39` from `planned` to `implemented`.

### Allowed Paths
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/**`
- `src/quant_eam/ui/static/**`
- `tests/test_ui_mvp.py`
- `tests/test_ui_workflow_checkpoints_phase39.py`
- `docs/08_phases/phase_59_*.md`
- `docs/12_workflows/agents_ui_ssot_v1.yaml`
- `artifacts/subagent_control/phase_59/**`

### Stop Conditions
- 触发 `autopilot_stop_conditions_v1` 任一项即暂停（仅 G39 exception 白名单范围内放行）。
- Subagent 禁止修改 `docs/12_workflows/agents_ui_ssot_v1.yaml`；仅主控在全部验收通过后回写 `G39.status_now=implemented`。

## 5) Subagent Control Packet
- `phase_id`: `phase_59`
- `packet_root`: `artifacts/subagent_control/phase_59/`
- `evidence_policy`: `hardened`

## 6) 验收标准（Acceptance Criteria / DoD）
- `docker compose run --rm api pytest -q tests/test_ui_workflow_checkpoints_phase39.py tests/test_ui_mvp.py`
- `python3 scripts/check_docs_tree.py`
- `python3 scripts/check_subagent_packet.py --phase-id phase_59`

## 7) 预期产物（Artifacts）
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/workflow_checkpoints.html`
- `tests/test_ui_workflow_checkpoints_phase39.py`
- `tests/test_ui_mvp.py`
- `artifacts/subagent_control/phase_59/task_card.yaml`
- `artifacts/subagent_control/phase_59/executor_report.yaml`
- `artifacts/subagent_control/phase_59/validator_report.yaml`

## 8) 完成记录（Execution Log）
- Start Date: 2026-02-12
- End Date: 2026-02-12
- Notes:
  - Published by orchestrator before subagent execution.
  - Task card enforces hardened evidence and G39 exception-scoped allowed paths.
  - Subagent implemented GET/HEAD route `/ui/workflow-checkpoints` with read-only template `workflow_checkpoints.html`.
  - Evidence rendering now combines Whole View section 3 workflow/checkpoints, Playbook section 3 phase flow text, and SSOT `orchestrator_autopilot_v1` + `phase_dispatch_plan_v2` + `agents_pipeline_v1`.
  - Added regression coverage in `tests/test_ui_workflow_checkpoints_phase39.py` and extended `tests/test_ui_mvp.py` smoke checks for `/ui/workflow-checkpoints`.
  - Acceptance passed: `docker compose run --rm api pytest -q tests/test_ui_workflow_checkpoints_phase39.py tests/test_ui_mvp.py`, `python3 scripts/check_docs_tree.py`, `python3 scripts/check_subagent_packet.py --phase-id phase_59`.
  - Orchestrator reran acceptance + packet validation, then completed SSOT writeback: `G39.status_now=implemented`.
