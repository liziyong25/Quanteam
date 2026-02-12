# Phase-68: Playbook Construction Principles and Quality Gates Evidence Page (G48)

## 1) 目标（Goal）
- 完成 G48：交付 `/ui/playbook-principles` 只读页面，展示《Quant‑EAM Implementation Phases Playbook》section 0/0.2 的施工原则与全局质量门槛证据。

## 2) 背景（Background）
- Playbook section 0 约束了单次 Codex 任务边界（改单模块、必须代码+测试+文档、contracts/policies 治理边界）。
- Playbook section 0.2 约束了全局质量门槛（pytest/schema 校验/一致性）。
- 无人值守执行需要将这些约束在 UI 中只读可审阅，作为实现治理基线。

## 3) 范围（Scope）
### In Scope
- 新增 `/ui/playbook-principles` 只读路由与模板渲染。
- 从 `Quant‑EAM Implementation Phases Playbook.md` section 0/0.2 提取施工原则与质量门槛证据。
- 增补 G48 回归测试覆盖只读语义、关键条目展示与可访问性。

### Out of Scope
- 修改 `contracts/**`。
- 修改 `policies/**`。
- 扩展 holdout 可见性。
- 新增写接口或修改非 G48 范围路由行为。

## 4) 任务卡（Task Card）
### Single Deliverable
- `G48` from `planned` to `implemented`.

### Allowed Paths
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/**`
- `src/quant_eam/ui/static/**`
- `tests/test_ui_mvp.py`
- `tests/test_ui_playbook_principles_phase48.py`
- `docs/08_phases/phase_68_*.md`
- `docs/12_workflows/agents_ui_ssot_v1.yaml`
- `artifacts/subagent_control/phase_68/**`

### Stop Conditions
- 触发 `autopilot_stop_conditions_v1` 任一项即暂停（仅 G48 exception 白名单范围内放行）。
- Subagent 禁止修改 `docs/12_workflows/agents_ui_ssot_v1.yaml`；仅主控在全部验收通过后回写 `G48.status_now=implemented`。

## 5) Subagent Control Packet
- `phase_id`: `phase_68`
- `packet_root`: `artifacts/subagent_control/phase_68/`
- `evidence_policy`: `hardened`

## 6) 验收标准（Acceptance Criteria / DoD）
- `docker compose run --rm api pytest -q tests/test_ui_playbook_principles_phase48.py tests/test_ui_mvp.py`
- `python3 scripts/check_docs_tree.py`
- `python3 scripts/check_subagent_packet.py --phase-id phase_68`

## 7) 预期产物（Artifacts）
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/playbook_principles.html`
- `tests/test_ui_playbook_principles_phase48.py`
- `tests/test_ui_mvp.py`
- `artifacts/subagent_control/phase_68/task_card.yaml`
- `artifacts/subagent_control/phase_68/executor_report.yaml`
- `artifacts/subagent_control/phase_68/validator_report.yaml`

## 8) 完成记录（Execution Log）
- Start Date: 2026-02-12
- End Date: 2026-02-12
- Notes:
  - Published by orchestrator before subagent execution.
  - Task card enforces hardened evidence and G48 exception-scoped allowed paths.

## 9) Implementation Notes (Subagent)
- Added read-only route `GET/HEAD /ui/playbook-principles` in `src/quant_eam/api/ui_routes.py`.
- Added scoped extraction for Playbook section `0` and subsection `0.2` only, with no SSOT/policy/contract write behavior changes.
- Added read-only template `src/quant_eam/ui/templates/playbook_principles.html` with governance-boundary pills and evidence tables.
- Added regression test `tests/test_ui_playbook_principles_phase48.py` and extended `tests/test_ui_mvp.py` smoke coverage for `/ui/playbook-principles`.

## 10) Acceptance Notes
- Required acceptance commands executed successfully in subagent workspace and rerun by orchestrator:
  - `docker compose run --rm api pytest -q tests/test_ui_playbook_principles_phase48.py tests/test_ui_mvp.py`
  - `python3 scripts/check_docs_tree.py`
  - `python3 scripts/check_subagent_packet.py --phase-id phase_68`
- Subagent governance boundary preserved: `docs/12_workflows/agents_ui_ssot_v1.yaml` was not modified by subagent.
- Orchestrator writeback completed: `docs/12_workflows/agents_ui_ssot_v1.yaml` updated with `G48.status_now=implemented`; `artifacts/subagent_control/phase_68/validator_report.yaml` finalized to `status=pass`.
