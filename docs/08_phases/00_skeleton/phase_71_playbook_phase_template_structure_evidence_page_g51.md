# Phase-71: Playbook Phase Template Structure Evidence Page (G51)

## 1) 目标（Goal）
- 完成 G51：交付 `/ui/playbook-phase-template` 只读页面，展示《Quant‑EAM Implementation Phases Playbook》section 2 与 Phase‑X 标准输出结构证据。

## 2) 背景（Background）
- Playbook section 2 定义了 phase 任务书模板，是无人值守编排时的标准化输入。
- 该模板结构需在 UI 中可审阅，以确保后续 phase 制定遵循统一格式。

## 3) 范围（Scope）
### In Scope
- 新增 `/ui/playbook-phase-template` 只读路由与模板渲染。
- 从 `Quant‑EAM Implementation Phases Playbook.md` section 2 提取模板结构证据。
- 增补 G51 回归测试覆盖只读语义、关键结构展示与可访问性。

### Out of Scope
- 修改 `contracts/**`。
- 修改 `policies/**`。
- 扩展 holdout 可见性。
- 新增写接口或修改非 G51 范围路由行为。

## 4) 任务卡（Task Card）
### Single Deliverable
- `G51` from `planned` to `implemented`.

### Allowed Paths
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/**`
- `src/quant_eam/ui/static/**`
- `tests/test_ui_mvp.py`
- `tests/test_ui_playbook_phase_template_phase51.py`
- `docs/08_phases/00_skeleton/phase_71_*.md`
- `docs/12_workflows/skeleton_ssot_v1.yaml`
- `artifacts/subagent_control/phase_71/**`

### Stop Conditions
- 触发 `autopilot_stop_conditions_v1` 任一项即暂停（仅 G51 exception 白名单范围内放行）。
- Subagent 禁止修改 `docs/12_workflows/skeleton_ssot_v1.yaml`；仅主控在全部验收通过后回写 `G51.status_now=implemented`。

## 5) Subagent Control Packet
- `phase_id`: `phase_71`
- `packet_root`: `artifacts/subagent_control/phase_71/`
- `evidence_policy`: `hardened`

## 6) 验收标准（Acceptance Criteria / DoD）
- `docker compose run --rm api pytest -q tests/test_ui_playbook_phase_template_phase51.py tests/test_ui_mvp.py`
- `python3 scripts/check_docs_tree.py`
- `python3 scripts/check_subagent_packet.py --phase-id phase_71`

## 7) 预期产物（Artifacts）
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/playbook_phase_template.html`
- `tests/test_ui_playbook_phase_template_phase51.py`
- `tests/test_ui_mvp.py`
- `artifacts/subagent_control/phase_71/task_card.yaml`
- `artifacts/subagent_control/phase_71/executor_report.yaml`
- `artifacts/subagent_control/phase_71/validator_report.yaml`

## 8) 完成记录（Execution Log）
- Start Date: 2026-02-12
- End Date: 2026-02-12
- Notes:
  - Published by orchestrator before subagent execution.
  - Task card enforces hardened evidence and G51 exception-scoped allowed paths.
  - Implemented `/ui/playbook-phase-template` as a read-only evidence page with section-2-only extraction from `Quant‑EAM Implementation Phases Playbook.md`, plus template rendering and route wiring in UI scope.
  - Added/updated regression coverage: `tests/test_ui_playbook_phase_template_phase51.py` and `tests/test_ui_mvp.py` for route availability, section-2 structure evidence, and no-write semantics.
  - Acceptance outcome: required pytest/docs/packet commands passed (including orchestrator rerun).
  - Orchestrator writeback completed: `docs/12_workflows/skeleton_ssot_v1.yaml` updated with `G51.status_now=implemented`; validator finalized to `status=pass`.
