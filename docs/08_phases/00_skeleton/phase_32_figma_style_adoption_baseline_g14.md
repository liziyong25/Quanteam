# Phase-32: Figma-Design Style Adoption Baseline (G14)

## 1) 目标（Goal）
- 完成 G14：在不改业务/API 的前提下，按 `figma-design` 方法建立 UI 设计 token 与组件样式基线。

## 2) 背景（Background）
- G14 依赖 G13，已满足。
- SSOT 要求 `frontend_style_method_v1`：以 `figma-design` 作为方法参考，采用 token + component mapping。

## 3) 范围（Scope）
### In Scope
- 在 `ui.css` 建立与 figma-design 风格方法对应的 token 层（颜色/字体/间距/圆角/动效）。
- 模板类名映射到统一组件类（按钮、卡片、表格、页头）。
- 保持桌面与移动端可用。

### Out of Scope
- API/路由变更。
- contracts/policies 变更。
- Prompt Studio 功能实现（G11）。
- Trace Preview K-line 叠加功能（G05）。

## 4) 任务卡（Task Card）
### Single Deliverable
- G14 `planned -> implemented`。

### Allowed Paths
- `src/quant_eam/ui/templates/**`
- `src/quant_eam/ui/static/**`
- `tests/test_ui_mvp.py`
- `docs/08_phases/00_skeleton/phase_32_figma_style_adoption_baseline_g14.md`
- `docs/12_workflows/skeleton_ssot_v1.yaml`
- `artifacts/subagent_control/phase_32/**`

### Stop Conditions
- 触发 `autopilot_stop_conditions_v1` 任一项即暂停并上报用户。

## 5) Subagent Control Packet
- `phase_id`: `phase_32`
- `packet_root`: `artifacts/subagent_control/phase_32/`
- Required:
  - `task_card.yaml`
  - `executor_report.yaml`
  - `validator_report.yaml`

## 6) 验收标准（Acceptance Criteria / DoD）
- `docker compose run --rm api pytest -q tests/test_ui_mvp.py`
- `python3 scripts/check_docs_tree.py`
- `python3 scripts/check_subagent_packet.py --phase-id phase_32`

## 7) 预期产物（Artifacts）
- `src/quant_eam/ui/static/ui.css` 出现 token/component baseline。
- `artifacts/subagent_control/phase_32/task_card.yaml`
- `artifacts/subagent_control/phase_32/executor_report.yaml`
- `artifacts/subagent_control/phase_32/validator_report.yaml`
- `docs/12_workflows/skeleton_ssot_v1.yaml` 中 `G14.status_now=implemented`

## 8) 完成记录（Execution Log）
- Start Date: 2026-02-11
- End Date: 2026-02-11
- Notes:
  - Published by orchestrator before subagent execution.
  - Executor 在 `src/quant_eam/ui/static/ui.css` 完成 figma-design 方法映射：建立颜色/字体/间距/圆角/动效 token，并将 page header/card/table/form/button 组件样式统一到 token 层。
  - Executor 在 `src/quant_eam/ui/templates/job.html` 补齐审批/Spawn 相关表单的统一 `form-inline` 组件类，保持动作 URL 与业务语义不变。
  - Acceptance 通过：`docker compose run --rm api pytest -q tests/test_ui_mvp.py`（4 passed）与 `python3 scripts/check_docs_tree.py`（docs tree: OK）。

## 9) 遗留问题（Open Issues）
- [ ] 在后续前端 phase 继续沿用 token/component mapping 规则。
