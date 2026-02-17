# Phase-61: Whole View Modules Deterministic-Agent Boundary Page (G41)

## 1) 目标（Goal）
- 完成 G41：交付 `/ui/module-boundaries` 只读页面，展示 Whole View section 6 的模块职责与 deterministic/agent 边界治理证据。

## 2) 背景（Background）
- Whole View section 6 明确 Data Plane、Backtest Plane、Deterministic Kernel、Agents Plane 的职责分层。
- 无人值守流程要求将模块边界与裁判权约束可视化为只读证据，确保系统不跑偏。

## 3) 范围（Scope）
### In Scope
- 新增 `/ui/module-boundaries` 只读路由和模板渲染。
- 从 Whole View + Playbook 提取模块职责边界证据并映射 SSOT 相关结构。
- 增补 G41 回归测试覆盖可访问性、只读语义与关键边界字段展示。

### Out of Scope
- 修改 `contracts/**`。
- 修改 `policies/**`。
- 扩展 holdout 可见性。
- 新增写接口或修改非 G41 范围路由行为。

## 4) 任务卡（Task Card）
### Single Deliverable
- `G41` from `planned` to `implemented`.

### Allowed Paths
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/**`
- `src/quant_eam/ui/static/**`
- `tests/test_ui_mvp.py`
- `tests/test_ui_module_boundaries_phase41.py`
- `docs/08_phases/00_skeleton/phase_61_*.md`
- `docs/12_workflows/skeleton_ssot_v1.yaml`
- `artifacts/subagent_control/phase_61/**`

### Stop Conditions
- 触发 `autopilot_stop_conditions_v1` 任一项即暂停（仅 G41 exception 白名单范围内放行）。
- Subagent 禁止修改 `docs/12_workflows/skeleton_ssot_v1.yaml`；仅主控在全部验收通过后回写 `G41.status_now=implemented`。

## 5) Subagent Control Packet
- `phase_id`: `phase_61`
- `packet_root`: `artifacts/subagent_control/phase_61/`
- `evidence_policy`: `hardened`

## 6) 验收标准（Acceptance Criteria / DoD）
- `docker compose run --rm api pytest -q tests/test_ui_module_boundaries_phase41.py tests/test_ui_mvp.py`
- `python3 scripts/check_docs_tree.py`
- `python3 scripts/check_subagent_packet.py --phase-id phase_61`

## 7) 预期产物（Artifacts）
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/module_boundaries.html`
- `tests/test_ui_module_boundaries_phase41.py`
- `tests/test_ui_mvp.py`
- `artifacts/subagent_control/phase_61/task_card.yaml`
- `artifacts/subagent_control/phase_61/executor_report.yaml`
- `artifacts/subagent_control/phase_61/validator_report.yaml`

## 8) 完成记录（Execution Log）
- Start Date: 2026-02-12
- End Date: 2026-02-12
- Notes:
  - Published by orchestrator before subagent execution.
  - Task card enforces hardened evidence and G41 exception-scoped allowed paths.
  - Subagent implemented `GET/HEAD`-only route `/ui/module-boundaries` in `src/quant_eam/api/ui_routes.py`, with read-only template `src/quant_eam/ui/templates/module_boundaries.html`.
  - Evidence rendering is sourced from:
    - `docs/00_overview/Quant‑EAM Whole View Framework.md` section `6. 模块（Modules）与职责边界（Deterministic vs Agent）`
    - `docs/00_overview/Quant‑EAM Implementation Phases Playbook.md` section `3. Phase 列表（推荐施工顺序）`
    - `docs/12_workflows/skeleton_ssot_v1.yaml` entries `goal_checklist(G41)` / `phase_dispatch_plan_v2` / `g41_module_boundaries_ui_scope` / `agents_pipeline_v1`
  - Added regression coverage in `tests/test_ui_module_boundaries_phase41.py` and extended `tests/test_ui_mvp.py` smoke checks for `/ui/module-boundaries`.
  - Governance boundary preserved on page render: `GET/HEAD only`, `no write actions`, `no holdout expansion`, and no write controls exposed.
  - Acceptance executed and passed:
    - `docker compose run --rm api pytest -q tests/test_ui_module_boundaries_phase41.py tests/test_ui_mvp.py`
    - `python3 scripts/check_docs_tree.py`
    - `python3 scripts/check_subagent_packet.py --phase-id phase_61`
  - Orchestrator reran acceptance + packet validation, then completed SSOT writeback: `G41.status_now=implemented`.
