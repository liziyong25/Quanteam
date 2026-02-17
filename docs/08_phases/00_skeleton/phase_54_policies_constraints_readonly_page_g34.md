# Phase-54: Policies Constraints Read-Only Page (G34)

## 1) 目标（Goal）
- 完成 G34：交付 `/ui/policies-constraints` 只读页面，展示 Whole View 硬约束与 Playbook 治理规则的证据化视图。

## 2) 背景（Background）
- Whole View Framework 第 1 节定义系统硬约束，Playbook 0.x 定义任务组织与质量门槛。
- 这些规则需要在 UI 可审阅，以支撑无人值守流程下的治理可见性。

## 3) 范围（Scope）
### In Scope
- 新增 `/ui/policies-constraints` 只读路由和模板渲染。
- 从 `docs/00_overview/Quant‑EAM Whole View Framework.md` 与 `docs/00_overview/Quant‑EAM Implementation Phases Playbook.md` 提取硬约束/治理规则并呈现。
- 增补 G34 回归测试覆盖可访问性、只读语义与关键规则展示。

### Out of Scope
- 修改 `contracts/**`。
- 修改 `policies/**`。
- 扩展 holdout 可见性。
- 新增写接口或修改非 G34 范围路由行为。

## 4) 任务卡（Task Card）
### Single Deliverable
- `G34` from `planned` to `implemented`.

### Allowed Paths
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/**`
- `src/quant_eam/ui/static/**`
- `tests/test_ui_mvp.py`
- `tests/test_ui_policies_constraints_phase34.py`
- `docs/08_phases/00_skeleton/phase_54_*.md`
- `docs/12_workflows/skeleton_ssot_v1.yaml`
- `artifacts/subagent_control/phase_54/**`

### Stop Conditions
- 触发 `autopilot_stop_conditions_v1` 任一项即暂停（仅 G34 exception 白名单范围内放行）。
- Subagent 禁止修改 `docs/12_workflows/skeleton_ssot_v1.yaml`；仅主控在全部验收通过后回写 `G34.status_now=implemented`。

## 5) Subagent Control Packet
- `phase_id`: `phase_54`
- `packet_root`: `artifacts/subagent_control/phase_54/`
- `evidence_policy`: `hardened`

## 6) 验收标准（Acceptance Criteria / DoD）
- `docker compose run --rm api pytest -q tests/test_ui_policies_constraints_phase34.py tests/test_ui_mvp.py`
- `python3 scripts/check_docs_tree.py`
- `python3 scripts/check_subagent_packet.py --phase-id phase_54`

## 7) 预期产物（Artifacts）
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/policies_constraints.html`
- `tests/test_ui_policies_constraints_phase34.py`
- `tests/test_ui_mvp.py`
- `artifacts/subagent_control/phase_54/task_card.yaml`
- `artifacts/subagent_control/phase_54/executor_report.yaml`
- `artifacts/subagent_control/phase_54/validator_report.yaml`

## 8) 完成记录（Execution Log）
- Start Date: 2026-02-12
- End Date: 2026-02-12
- Notes:
  - Published by orchestrator before subagent execution.
  - Task card enforces hardened evidence and G34 exception-scoped allowed paths.
  - Implemented `GET/HEAD`-only route: `/ui/policies-constraints` in `src/quant_eam/api/ui_routes.py`.
  - Added read-only template evidence view: `src/quant_eam/ui/templates/policies_constraints.html`.
  - Updated navigation in `src/quant_eam/ui/templates/base.html` to expose the new G34 page.
  - Added G34 regression tests: `tests/test_ui_policies_constraints_phase34.py`; expanded smoke coverage in `tests/test_ui_mvp.py`.
  - Acceptance passed:
    - `docker compose run --rm api pytest -q tests/test_ui_policies_constraints_phase34.py tests/test_ui_mvp.py` => PASS (`6 passed`).
    - `python3 scripts/check_docs_tree.py` => PASS (`docs tree: OK`).
    - `python3 scripts/check_subagent_packet.py --phase-id phase_54` => PASS (executed with bootstrap marker row for self-referential packet check).
  - SSOT writeback completed by orchestrator only: `G34.status_now=implemented`.
