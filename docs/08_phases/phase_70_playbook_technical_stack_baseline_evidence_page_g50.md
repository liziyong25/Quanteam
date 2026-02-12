# Phase-70: Playbook Technical Stack Baseline Evidence Page (G50)

## 1) 目标（Goal）
- 完成 G50：交付 `/ui/playbook-tech-stack` 只读页面，展示《Quant‑EAM Implementation Phases Playbook》section 1/1.1/1.2 技术栈基线证据。

## 2) 背景（Background）
- Playbook section 1 定义了基础技术栈建议；section 1.1/1.2 明确基础与服务层建议。
- 在无人值守演进中，这些基线需要在 UI 可视化呈现，作为实施一致性核对依据。

## 3) 范围（Scope）
### In Scope
- 新增 `/ui/playbook-tech-stack` 只读路由与模板渲染。
- 从 `Quant‑EAM Implementation Phases Playbook.md` section 1/1.1/1.2 提取技术栈证据。
- 增补 G50 回归测试覆盖只读语义、关键条目展示与可访问性。

### Out of Scope
- 修改 `contracts/**`。
- 修改 `policies/**`。
- 扩展 holdout 可见性。
- 新增写接口或修改非 G50 范围路由行为。

## 4) 任务卡（Task Card）
### Single Deliverable
- `G50` from `planned` to `implemented`.

### Allowed Paths
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/**`
- `src/quant_eam/ui/static/**`
- `tests/test_ui_mvp.py`
- `tests/test_ui_playbook_tech_stack_phase50.py`
- `docs/08_phases/phase_70_*.md`
- `docs/12_workflows/agents_ui_ssot_v1.yaml`
- `artifacts/subagent_control/phase_70/**`

### Stop Conditions
- 触发 `autopilot_stop_conditions_v1` 任一项即暂停（仅 G50 exception 白名单范围内放行）。
- Subagent 禁止修改 `docs/12_workflows/agents_ui_ssot_v1.yaml`；仅主控在全部验收通过后回写 `G50.status_now=implemented`。

## 5) Subagent Control Packet
- `phase_id`: `phase_70`
- `packet_root`: `artifacts/subagent_control/phase_70/`
- `evidence_policy`: `hardened`

## 6) 验收标准（Acceptance Criteria / DoD）
- `docker compose run --rm api pytest -q tests/test_ui_playbook_tech_stack_phase50.py tests/test_ui_mvp.py`
- `python3 scripts/check_docs_tree.py`
- `python3 scripts/check_subagent_packet.py --phase-id phase_70`

## 7) 预期产物（Artifacts）
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/playbook_tech_stack.html`
- `tests/test_ui_playbook_tech_stack_phase50.py`
- `tests/test_ui_mvp.py`
- `artifacts/subagent_control/phase_70/task_card.yaml`
- `artifacts/subagent_control/phase_70/executor_report.yaml`
- `artifacts/subagent_control/phase_70/validator_report.yaml`

## 8) 完成记录（Execution Log）
- Start Date: 2026-02-12
- End Date: 2026-02-12
- Notes:
  - Published by orchestrator before subagent execution.
  - Task card enforces hardened evidence and G50 exception-scoped allowed paths.
  - Implementation: added read-only `/ui/playbook-tech-stack` route + template using only Playbook section 1/1.1/1.2 extraction, and added phase-specific/UI-MVP regression coverage.
  - Acceptance outcome: executed required `pytest`, `check_docs_tree`, and `check_subagent_packet` commands with successful results recorded in phase packet acceptance log.
  - Orchestrator writeback completed: `docs/12_workflows/agents_ui_ssot_v1.yaml` updated with `G50.status_now=implemented`; `artifacts/subagent_control/phase_70/validator_report.yaml` finalized to `status=pass`.
