# Phase-72: Playbook Codex Task Card Template Evidence Page (G52)

## 1) 目标（Goal）
- 完成 G52：交付 `/ui/playbook-codex-task-card` 只读页面，展示《Quant‑EAM Implementation Phases Playbook》section 4 的 Codex Task Card Template 证据。

## 2) 背景（Background）
- Playbook section 4 提供了标准 Codex 任务卡模板，是无人值守任务发包的重要规范。
- 该模板需在 UI 中只读可审阅，确保主控发包遵循同一结构标准。

## 3) 范围（Scope）
### In Scope
- 新增 `/ui/playbook-codex-task-card` 只读路由与模板渲染。
- 从 `Quant‑EAM Implementation Phases Playbook.md` section 4 提取 Codex 任务卡模板证据。
- 增补 G52 回归测试覆盖只读语义、关键结构展示与可访问性。

### Out of Scope
- 修改 `contracts/**`。
- 修改 `policies/**`。
- 扩展 holdout 可见性。
- 新增写接口或修改非 G52 范围路由行为。

## 4) 任务卡（Task Card）
### Single Deliverable
- `G52` from `planned` to `implemented`.

### Allowed Paths
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/**`
- `src/quant_eam/ui/static/**`
- `tests/test_ui_mvp.py`
- `tests/test_ui_playbook_codex_task_card_phase52.py`
- `docs/08_phases/phase_72_*.md`
- `docs/12_workflows/agents_ui_ssot_v1.yaml`
- `artifacts/subagent_control/phase_72/**`

### Stop Conditions
- 触发 `autopilot_stop_conditions_v1` 任一项即暂停（仅 G52 exception 白名单范围内放行）。
- Subagent 禁止修改 `docs/12_workflows/agents_ui_ssot_v1.yaml`；仅主控在全部验收通过后回写 `G52.status_now=implemented`。

## 5) Subagent Control Packet
- `phase_id`: `phase_72`
- `packet_root`: `artifacts/subagent_control/phase_72/`
- `evidence_policy`: `hardened`

## 6) 验收标准（Acceptance Criteria / DoD）
- `docker compose run --rm api pytest -q tests/test_ui_playbook_codex_task_card_phase52.py tests/test_ui_mvp.py`
- `python3 scripts/check_docs_tree.py`
- `python3 scripts/check_subagent_packet.py --phase-id phase_72`

## 7) 预期产物（Artifacts）
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/playbook_codex_task_card.html`
- `tests/test_ui_playbook_codex_task_card_phase52.py`
- `tests/test_ui_mvp.py`
- `artifacts/subagent_control/phase_72/task_card.yaml`
- `artifacts/subagent_control/phase_72/executor_report.yaml`
- `artifacts/subagent_control/phase_72/validator_report.yaml`

## 8) 完成记录（Execution Log）
- Start Date: 2026-02-12
- End Date: 2026-02-12
- Notes:
  - Published by orchestrator before subagent execution.
  - Task card enforces hardened evidence and G52 exception-scoped allowed paths.
  - Implemented `/ui/playbook-codex-task-card` as a read-only evidence page with section-4-only extraction from `Quant‑EAM Implementation Phases Playbook.md` (Codex Task Card Template fields, must-implement list, forbidden list, acceptance command list).
  - Added/updated regression coverage: `tests/test_ui_playbook_codex_task_card_phase52.py` and `tests/test_ui_mvp.py` for route availability, section-4 structure evidence, and no-write semantics.
  - Acceptance outcome: required pytest/docs/packet commands passed.
  - Subagent pre-writeback status kept: `validator_report.checks[name=ssot_updated].pass=false`; SSOT writeback remains orchestrator-owned.
  - Orchestrator finalized writeback: `docs/12_workflows/agents_ui_ssot_v1.yaml` updated to `G52.status_now=implemented`; `validator_report.yaml` promoted to final pass state.
