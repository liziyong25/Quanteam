# Phase-58: Agents Roles Harness Boundary Page (G38)

## 1) 目标（Goal）
- 完成 G38：交付 `/ui/agent-roles` 只读页面，展示 agents roles、harness 边界与治理规则证据。

## 2) 背景（Background）
- Whole View section 6.4 与 Playbook phase-8 描述 agents 角色与边界。
- 无人值守流程需要将角色职责、输入输出与限制条件可视化为只读证据。

## 3) 范围（Scope）
### In Scope
- 新增 `/ui/agent-roles` 只读路由和模板渲染。
- 从 Whole View + Playbook 文档提取角色与边界规则并映射 SSOT agents_pipeline。
- 增补 G38 回归测试覆盖可访问性、只读语义与关键字段展示。

### Out of Scope
- 修改 `contracts/**`。
- 修改 `policies/**`。
- 扩展 holdout 可见性。
- 新增写接口或修改非 G38 范围路由行为。

## 4) 任务卡（Task Card）
### Single Deliverable
- `G38` from `planned` to `implemented`.

### Allowed Paths
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/**`
- `src/quant_eam/ui/static/**`
- `tests/test_ui_mvp.py`
- `tests/test_ui_agent_roles_phase38.py`
- `docs/08_phases/phase_58_*.md`
- `docs/12_workflows/agents_ui_ssot_v1.yaml`
- `artifacts/subagent_control/phase_58/**`

### Stop Conditions
- 触发 `autopilot_stop_conditions_v1` 任一项即暂停（仅 G38 exception 白名单范围内放行）。
- Subagent 禁止修改 `docs/12_workflows/agents_ui_ssot_v1.yaml`；仅主控在全部验收通过后回写 `G38.status_now=implemented`。

## 5) Subagent Control Packet
- `phase_id`: `phase_58`
- `packet_root`: `artifacts/subagent_control/phase_58/`
- `evidence_policy`: `hardened`

## 6) 验收标准（Acceptance Criteria / DoD）
- `docker compose run --rm api pytest -q tests/test_ui_agent_roles_phase38.py tests/test_ui_mvp.py`
- `python3 scripts/check_docs_tree.py`
- `python3 scripts/check_subagent_packet.py --phase-id phase_58`

## 7) 预期产物（Artifacts）
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/agent_roles.html`
- `tests/test_ui_agent_roles_phase38.py`
- `tests/test_ui_mvp.py`
- `artifacts/subagent_control/phase_58/task_card.yaml`
- `artifacts/subagent_control/phase_58/executor_report.yaml`
- `artifacts/subagent_control/phase_58/validator_report.yaml`

## 8) 完成记录（Execution Log）
- Start Date: 2026-02-12
- End Date: 2026-02-12
- Notes:
  - Published by orchestrator before subagent execution.
  - Task card enforces hardened evidence and G38 exception-scoped allowed paths.
  - Implemented `GET/HEAD`-only route `/ui/agent-roles` in `src/quant_eam/api/ui_routes.py`, sourcing evidence from:
    - `docs/00_overview/Quant‑EAM Whole View Framework.md` section `6.4 Agents Plane（LLM + Codex，全部通过 harness 运行）`
    - `docs/00_overview/Quant‑EAM Implementation Phases Playbook.md` section `Phase‑8：Agents v1（Intent / StrategySpec / Spec‑QA / Report / Improvement）`
    - `docs/12_workflows/agents_ui_ssot_v1.yaml` section `agents_pipeline_v1`
  - Added template `src/quant_eam/ui/templates/agent_roles.html` and base navigation link in `src/quant_eam/ui/templates/base.html`.
  - Added regression coverage in `tests/test_ui_agent_roles_phase38.py` and expanded `tests/test_ui_mvp.py` smoke checks for `/ui/agent-roles`.
  - Governance boundary preserved on page render: `GET/HEAD only`, `no write actions`, `no holdout expansion`, and no write controls exposed.
  - Acceptance passed:
    - `docker compose run --rm api pytest -q tests/test_ui_agent_roles_phase38.py tests/test_ui_mvp.py` -> PASS (`6 passed, 48 warnings in 8.99s`).
    - `python3 scripts/check_docs_tree.py` -> PASS (`docs tree: OK`).
    - `python3 scripts/check_subagent_packet.py --phase-id phase_58` -> PASS (`subagent packet: OK`).
  - Orchestrator reran acceptance commands and packet validation, then completed SSOT writeback: `G38.status_now=implemented`.
