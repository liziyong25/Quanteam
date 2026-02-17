# Phase-62: Codex Diagnostics Promotion Chain Read-Only Page (G42)

## 1) 目标（Goal）
- 完成 G42：交付 `/ui/diagnostics-promotion` 只读页面，展示 Whole View section 7 的 diagnostics -> gate promotion 治理链路证据。

## 2) 背景（Background）
- Whole View section 7 明确 Codex 作为诊断探索者，裁判权仍由 deterministic gate runner 承担。
- 无人值守流程需将 diagnostics 提议、promote 条件、gate 发布路径可视化为只读治理证据。

## 3) 范围（Scope）
### In Scope
- 新增 `/ui/diagnostics-promotion` 只读路由和模板渲染。
- 从 Whole View + Playbook（phase-12）提取 diagnostics promotion 证据并映射 SSOT 相关条目。
- 增补 G42 回归测试覆盖可访问性、只读语义与关键治理字段展示。

### Out of Scope
- 修改 `contracts/**`。
- 修改 `policies/**`。
- 扩展 holdout 可见性。
- 新增写接口或修改非 G42 范围路由行为。

## 4) 任务卡（Task Card）
### Single Deliverable
- `G42` from `planned` to `implemented`.

### Allowed Paths
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/**`
- `src/quant_eam/ui/static/**`
- `tests/test_ui_mvp.py`
- `tests/test_ui_diagnostics_promotion_phase42.py`
- `docs/08_phases/00_skeleton/phase_62_*.md`
- `docs/12_workflows/skeleton_ssot_v1.yaml`
- `artifacts/subagent_control/phase_62/**`

### Stop Conditions
- 触发 `autopilot_stop_conditions_v1` 任一项即暂停（仅 G42 exception 白名单范围内放行）。
- Subagent 禁止修改 `docs/12_workflows/skeleton_ssot_v1.yaml`；仅主控在全部验收通过后回写 `G42.status_now=implemented`。

## 5) Subagent Control Packet
- `phase_id`: `phase_62`
- `packet_root`: `artifacts/subagent_control/phase_62/`
- `evidence_policy`: `hardened`

## 6) 验收标准（Acceptance Criteria / DoD）
- `docker compose run --rm api pytest -q tests/test_ui_diagnostics_promotion_phase42.py tests/test_ui_mvp.py`
- `python3 scripts/check_docs_tree.py`
- `python3 scripts/check_subagent_packet.py --phase-id phase_62`

## 7) 预期产物（Artifacts）
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/diagnostics_promotion.html`
- `tests/test_ui_diagnostics_promotion_phase42.py`
- `tests/test_ui_mvp.py`
- `artifacts/subagent_control/phase_62/task_card.yaml`
- `artifacts/subagent_control/phase_62/executor_report.yaml`
- `artifacts/subagent_control/phase_62/validator_report.yaml`

## 8) 完成记录（Execution Log）
- Start Date: 2026-02-12
- End Date: 2026-02-12
- Notes:
  - Published by orchestrator before subagent execution.
  - Task card enforces hardened evidence and G42 exception-scoped allowed paths.
  - Subagent implemented `GET/HEAD`-only route `/ui/diagnostics-promotion` in `src/quant_eam/api/ui_routes.py`, with read-only template `src/quant_eam/ui/templates/diagnostics_promotion.html`.
  - Evidence rendering is sourced from:
    - `docs/00_overview/Quant‑EAM Whole View Framework.md` section `7. Codex CLI 的定位：探索者 + 工具工，不是裁判`（含 `7.1` 与 `7.2`）
    - `docs/00_overview/Quant‑EAM Implementation Phases Playbook.md` `Phase-12：Diagnostics（Codex 提出验证方法）+ 晋升 Gate`
    - `docs/12_workflows/skeleton_ssot_v1.yaml` entries `goal_checklist(G42)` / `phase_dispatch_plan_v2` / `g42_diagnostics_promotion_ui_scope` / `agents_pipeline_v1`
  - Added regression coverage in `tests/test_ui_diagnostics_promotion_phase42.py` and extended `tests/test_ui_mvp.py` smoke checks for `/ui/diagnostics-promotion`.
  - Governance boundary preserved on page render: `GET/HEAD only`, `no write actions`, `no holdout expansion`, and no write controls exposed.
  - Acceptance executed and passed:
    - `docker compose run --rm api pytest -q tests/test_ui_diagnostics_promotion_phase42.py tests/test_ui_mvp.py`
    - `python3 scripts/check_docs_tree.py`
    - `python3 scripts/check_subagent_packet.py --phase-id phase_62`
  - Orchestrator reran acceptance + packet validation, then completed SSOT writeback: `G42.status_now=implemented`.
