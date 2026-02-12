# Phase-63: Whole View UI Eight-Page Coverage Matrix (G43)

## 1) 目标（Goal）
- 完成 G43：交付 `/ui/ui-coverage-matrix` 只读页面，展示 Whole View section 8 的八页 IA 清单与当前 UI 路由覆盖矩阵。

## 2) 背景（Background）
- Whole View section 8 明确了“不看源码”的 8 个审阅页面。
- 无人值守流程要求将 IA 覆盖状态持续可视化为治理证据，确保流程完整性可审计。

## 3) 范围（Scope）
### In Scope
- 新增 `/ui/ui-coverage-matrix` 只读路由与模板渲染。
- 从 Whole View section 8 与现有 UI routes 提取覆盖矩阵证据。
- 增补 G43 回归测试覆盖只读语义、字段展示与可访问性。

### Out of Scope
- 修改 `contracts/**`。
- 修改 `policies/**`。
- 扩展 holdout 可见性。
- 新增写接口或修改非 G43 范围路由行为。

## 4) 任务卡（Task Card）
### Single Deliverable
- `G43` from `planned` to `implemented`.

### Allowed Paths
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/**`
- `src/quant_eam/ui/static/**`
- `tests/test_ui_mvp.py`
- `tests/test_ui_coverage_matrix_phase43.py`
- `docs/08_phases/phase_63_*.md`
- `docs/12_workflows/agents_ui_ssot_v1.yaml`
- `artifacts/subagent_control/phase_63/**`

### Stop Conditions
- 触发 `autopilot_stop_conditions_v1` 任一项即暂停（仅 G43 exception 白名单范围内放行）。
- Subagent 禁止修改 `docs/12_workflows/agents_ui_ssot_v1.yaml`；仅主控在全部验收通过后回写 `G43.status_now=implemented`。

## 5) Subagent Control Packet
- `phase_id`: `phase_63`
- `packet_root`: `artifacts/subagent_control/phase_63/`
- `evidence_policy`: `hardened`

## 6) 验收标准（Acceptance Criteria / DoD）
- `docker compose run --rm api pytest -q tests/test_ui_coverage_matrix_phase43.py tests/test_ui_mvp.py`
- `python3 scripts/check_docs_tree.py`
- `python3 scripts/check_subagent_packet.py --phase-id phase_63`

## 7) 预期产物（Artifacts）
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/ui_coverage_matrix.html`
- `tests/test_ui_coverage_matrix_phase43.py`
- `tests/test_ui_mvp.py`
- `artifacts/subagent_control/phase_63/task_card.yaml`
- `artifacts/subagent_control/phase_63/executor_report.yaml`
- `artifacts/subagent_control/phase_63/validator_report.yaml`

## 8) 完成记录（Execution Log）
- Start Date: 2026-02-12
- End Date: 2026-02-12
- Notes:
  - Published by orchestrator before subagent execution.
  - Task card enforces hardened evidence and G43 exception-scoped allowed paths.
  - Implemented `GET/HEAD`-only route `/ui/ui-coverage-matrix` in `src/quant_eam/api/ui_routes.py`.
  - Added read-only template `src/quant_eam/ui/templates/ui_coverage_matrix.html` with evidence sourced from:
    - Whole View section `8. UI 信息架构（不看源码的审阅体验）` checklist.
    - Current UI route/view metadata from `IA_CHECKLIST_ROUTE_BINDINGS`, `IA_ROUTE_VIEW_CATALOG`, and router method map.
    - SSOT references `goal_checklist(G43)`, `phase_dispatch_plan_v2`, and `g43_ui_coverage_matrix_scope`.
  - Updated `src/quant_eam/ui/templates/base.html` navigation to include `/ui/ui-coverage-matrix`.
  - Added regression suite `tests/test_ui_coverage_matrix_phase43.py` and extended `tests/test_ui_mvp.py` coverage for G43 page render/read-only checks.
  - Acceptance passed:
    - `docker compose run --rm api pytest -q tests/test_ui_coverage_matrix_phase43.py tests/test_ui_mvp.py` -> PASS (`6 passed, 48 warnings`).
    - `python3 scripts/check_docs_tree.py` -> PASS (`docs tree: OK`).
    - `python3 scripts/check_subagent_packet.py --phase-id phase_63` -> PASS (bootstrap success marker row + real packet check recorded in acceptance log).
  - Orchestrator reran acceptance + packet validation, then completed SSOT writeback: `G43.status_now=implemented`.
