# Phase-45: Agents Plane Productization (Curator/Composer/Diagnostics Roles) (G25)

## 1) 目标（Goal）
- 完成 G25：将 Curator/Composer/Diagnostics 角色纳入 orchestrator 管理，并在 jobs UI 时间线与证据视图中可审计。

## 2) 背景（Background）
- 当前 jobs 流程已具备 intent/strategy/report/improvement 等 agent 证据链。
- G25 需要补齐三类角色在 orchestrator 中的受控执行与可见证据，且不改变 deterministic kernel 的 PASS/FAIL 仲裁边界。

## 3) 范围（Scope）
### In Scope
- 新增 diagnostics/registry_curator/composer 三个 agent 角色实现。
- 将新角色接入 harness 与 orchestrator 工作流。
- 在 jobs UI 证据视图中暴露新角色运行证据。
- 增加回归测试覆盖新角色证据链与 UI 可见性。

### Out of Scope
- 修改 `contracts/**` 或 `policies/**`。
- 扩展 holdout 可见性。

## 4) 任务卡（Task Card）
### Single Deliverable
- `G25` from `planned` to `implemented`.

### Allowed Paths
- `src/quant_eam/agents/**`
- `src/quant_eam/orchestrator/**`
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/**`
- `src/quant_eam/ui/static/**`
- `prompts/agents/**`
- `tests/test_agents_*.py`
- `docs/13_agents/**`
- `docs/08_phases/phase_45_agents_plane_productization_roles_g25.md`
- `docs/12_workflows/agents_ui_ssot_v1.yaml`
- `artifacts/subagent_control/phase_45/**`

### Stop Conditions
- 触发 `autopilot_stop_conditions_v1` 任一项即暂停（G25 exception 白名单范围内除外）。

## 5) Subagent Control Packet
- `phase_id`: `phase_45`
- `packet_root`: `artifacts/subagent_control/phase_45/`
- evidence_policy: `hardened`

## 6) 验收标准（Acceptance Criteria / DoD）
- `docker compose run --rm api pytest -q tests/test_agents_roles_phase25.py tests/test_agents_orchestrator_phase11_e2e.py tests/test_ui_mvp.py`
- `python3 scripts/check_docs_tree.py`
- `python3 scripts/check_subagent_packet.py --phase-id phase_45`

## 7) 预期产物（Artifacts）
- `jobs/<job_id>/outputs/agents/diagnostics_agent/agent_run.json`
- `jobs/<job_id>/outputs/agents/registry_curator/agent_run.json`
- `jobs/<job_id>/outputs/agents/composer_agent/agent_run.json`
- `jobs/<job_id>/events.jsonl`
- `artifacts/subagent_control/phase_45/task_card.yaml`
- `artifacts/subagent_control/phase_45/executor_report.yaml`
- `artifacts/subagent_control/phase_45/validator_report.yaml`

## 8) 完成记录（Execution Log）
- Start Date: 2026-02-11
- End Date: 2026-02-11
- Notes:
  - Published by orchestrator before subagent execution.
  - Added diagnostics/registry_curator/composer role agents with deterministic evidence outputs.
  - Extended harness to support three new role agent IDs and promptpacks.
  - Integrated role execution into orchestrator workflow after registry stage with append-only event evidence.
  - Extended jobs UI evidence view to surface new role agent outputs and plans.
  - Added regression coverage in `tests/test_agents_roles_phase25.py`.
