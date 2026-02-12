# Phase-31: Frontend Foundation Refactor (G13)

## 1) 目标（Goal）
- 完成 G13：先做前端结构层重构（模板结构与样式基础层），不改变业务流程与 API 行为。

## 2) 背景（Background）
- SSOT 要求先完成 G13，再进入 G14/G05/G11。
- G13 定位为“structure first”，用于后续 figma-design 样式映射打底。

## 3) 范围（Scope）
### In Scope
- 统一 UI 模板基础结构（布局容器、区块骨架、通用 class 语义）。
- CSS 增加结构层基类（不引入新的业务逻辑）。
- 保持现有路由、数据字段、交互语义不变。

### Out of Scope
- API 变更、contracts/policies 变更。
- Prompt Studio 功能实现（G11）。
- Trace Preview K-line 叠加功能（G05）。

## 4) 任务卡（Task Card）
### Single Deliverable
- G13 `planned -> implemented`。

### Allowed Paths
- `src/quant_eam/ui/templates/**`
- `src/quant_eam/ui/static/**`
- `tests/test_ui_mvp.py`
- `docs/08_phases/00_skeleton/phase_31_frontend_foundation_refactor_g13.md`
- `docs/12_workflows/skeleton_ssot_v1.yaml`
- `artifacts/subagent_control/phase_31/**`

### Stop Conditions
- 触发 `autopilot_stop_conditions_v1` 任一项即暂停并上报用户。

## 5) Subagent Control Packet
- `phase_id`: `phase_31`
- `packet_root`: `artifacts/subagent_control/phase_31/`
- Required:
  - `task_card.yaml`
  - `executor_report.yaml`
  - `validator_report.yaml`

## 6) 验收标准（Acceptance Criteria / DoD）
- `docker compose run --rm api pytest -q tests/test_ui_mvp.py`
- `python3 scripts/check_docs_tree.py`
- `python3 scripts/check_subagent_packet.py --phase-id phase_31`

## 7) 预期产物（Artifacts）
- `artifacts/subagent_control/phase_31/task_card.yaml`
- `artifacts/subagent_control/phase_31/executor_report.yaml`
- `artifacts/subagent_control/phase_31/validator_report.yaml`
- `docs/12_workflows/skeleton_ssot_v1.yaml` 中 `G13.status_now=implemented`

## 8) 完成记录（Execution Log）
- Start Date: 2026-02-11
- End Date: 2026-02-11
- Notes:
  - Published by orchestrator before subagent execution.
  - Executor 完成模板结构层归一：增加页面头部/容器语义类、表格包裹层、按钮基础类，未改动路由与表单动作。
  - Executor 完成基础 CSS 扩展：补充 `page-*`、`table-wrap`、`btn`、`code`、`form-inline` 等通用类并保持现有视觉方向。
  - Acceptance 命令通过：`docker compose run --rm api pytest -q tests/test_ui_mvp.py` 与 `python3 scripts/check_docs_tree.py`。

## 9) 遗留问题（Open Issues）
- [ ] 在 G14 中完成 figma-design token/component 的视觉映射基线。
