# Phase-33: Trace Preview K-line Overlay (G05)

## 1) 目标（Goal）
- 完成 G05 剩余项：在 `/ui/jobs/<job_id>` 的 Trace Preview 区块提供 K-line Overlay 视觉层。

## 2) 背景（Background）
- SSOT 中 G05 目前为 `partial`，已实现 Trace 表格，未实现 K-line overlay。
- 本 phase 仅补齐 UI 审阅能力，不修改流程状态机与 API 合同。

## 3) 范围（Scope）
### In Scope
- 在 job 页面 Trace Preview 区块增加 K-line overlay 视图。
- 基于现有 `trace_preview_rows` 数据做前端渲染，不新增后端路由字段。
- 增加回归测试，确保关键元素可见。

### Out of Scope
- 任何 API schema/route behavior 变更。
- 任何 contracts/policies 变更。
- Prompt Studio 功能实现（G11）。

## 4) 任务卡（Task Card）
### Single Deliverable
- G05 `partial -> implemented`。

### Allowed Paths
- `src/quant_eam/ui/templates/**`
- `src/quant_eam/ui/static/**`
- `tests/test_ui_mvp.py`
- `tests/test_agents_orchestrator_phase11_e2e.py`
- `docs/08_phases/phase_33_trace_preview_kline_overlay_g05.md`
- `docs/12_workflows/agents_ui_ssot_v1.yaml`
- `artifacts/subagent_control/phase_33/**`

### Stop Conditions
- 触发 `autopilot_stop_conditions_v1` 任一项即暂停并上报用户。

## 5) Subagent Control Packet
- `phase_id`: `phase_33`
- `packet_root`: `artifacts/subagent_control/phase_33/`
- Required:
  - `task_card.yaml`
  - `executor_report.yaml`
  - `validator_report.yaml`

## 6) 验收标准（Acceptance Criteria / DoD）
- `docker compose run --rm api pytest -q tests/test_ui_mvp.py tests/test_agents_orchestrator_phase11_e2e.py`
- `python3 scripts/check_docs_tree.py`
- `python3 scripts/check_subagent_packet.py --phase-id phase_33`

## 7) 预期产物（Artifacts）
- Job 页面渲染 Trace Preview K-line Overlay（仅在 trace preview rows 存在时显示）。
- `artifacts/subagent_control/phase_33/task_card.yaml`
- `artifacts/subagent_control/phase_33/executor_report.yaml`
- `artifacts/subagent_control/phase_33/validator_report.yaml`
- `docs/12_workflows/agents_ui_ssot_v1.yaml` 中 `G05.status_now=implemented`

## 8) 完成记录（Execution Log）
- Start Date: 2026-02-11
- End Date: 2026-02-11
- Notes:
  - Published by orchestrator before subagent execution.
  - Executor 在 `job.html` 新增基于 `trace_preview_rows` 的 deterministic K-line overlay（保留原 Trace 表格）。
  - Executor 在 `ui.css` 新增 overlay 样式组件，并在移动端提供横向滚动兜底。
  - 验收通过：`docker compose run --rm api pytest -q tests/test_ui_mvp.py tests/test_agents_orchestrator_phase11_e2e.py`（5 passed）与 `python3 scripts/check_docs_tree.py`。

## 9) 遗留问题（Open Issues）
- [ ] 可选后续：增加可切换 symbol 的 overlay 视图。
