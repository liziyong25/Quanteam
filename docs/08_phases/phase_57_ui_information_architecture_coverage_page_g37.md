# Phase-57: UI Information Architecture Coverage Page (G37)

## 1) 目标（Goal）
- 完成 G37：交付 `/ui/ia-coverage` 只读页面，展示 Whole View section 8 的 IA 清单与当前 UI 路由覆盖映射。

## 2) 背景（Background）
- Whole View section 8 定义 UI 信息架构目标，需确保实现覆盖可追溯。
- 无人值守模式需要将 IA 覆盖作为只读治理证据，不依赖源码阅读。

## 3) 范围（Scope）
### In Scope
- 新增 `/ui/ia-coverage` 只读路由和模板渲染。
- 从 `docs/00_overview/Quant‑EAM Whole View Framework.md` section 8 提取 IA 条目并映射现有 UI routes。
- 增补 G37 回归测试覆盖可访问性、只读语义与覆盖统计展示。

### Out of Scope
- 修改 `contracts/**`。
- 修改 `policies/**`。
- 扩展 holdout 可见性。
- 新增写接口或修改非 G37 范围路由行为。

## 4) 任务卡（Task Card）
### Single Deliverable
- `G37` from `planned` to `implemented`.

### Allowed Paths
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/**`
- `src/quant_eam/ui/static/**`
- `tests/test_ui_mvp.py`
- `tests/test_ui_ia_coverage_phase37.py`
- `docs/08_phases/phase_57_*.md`
- `docs/12_workflows/agents_ui_ssot_v1.yaml`
- `artifacts/subagent_control/phase_57/**`

### Stop Conditions
- 触发 `autopilot_stop_conditions_v1` 任一项即暂停（仅 G37 exception 白名单范围内放行）。
- Subagent 禁止修改 `docs/12_workflows/agents_ui_ssot_v1.yaml`；仅主控在全部验收通过后回写 `G37.status_now=implemented`。

## 5) Subagent Control Packet
- `phase_id`: `phase_57`
- `packet_root`: `artifacts/subagent_control/phase_57/`
- `evidence_policy`: `hardened`

## 6) 验收标准（Acceptance Criteria / DoD）
- `docker compose run --rm api pytest -q tests/test_ui_ia_coverage_phase37.py tests/test_ui_mvp.py`
- `python3 scripts/check_docs_tree.py`
- `python3 scripts/check_subagent_packet.py --phase-id phase_57`

## 7) 预期产物（Artifacts）
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/ia_coverage.html`
- `tests/test_ui_ia_coverage_phase37.py`
- `tests/test_ui_mvp.py`
- `artifacts/subagent_control/phase_57/task_card.yaml`
- `artifacts/subagent_control/phase_57/executor_report.yaml`
- `artifacts/subagent_control/phase_57/validator_report.yaml`

## 8) 完成记录（Execution Log）
- Start Date: 2026-02-12
- End Date: 2026-02-12
- Notes:
  - Published by orchestrator before subagent execution.
  - Task card enforces hardened evidence and G37 exception-scoped allowed paths.
  - Implemented `GET/HEAD`-only route `/ui/ia-coverage` in `src/quant_eam/api/ui_routes.py`, sourced from Whole View section `8. UI 信息架构（不看源码的审阅体验）`.
  - Added IA checklist extraction + route/view coverage mapping evidence context, with governance boundary preserved (`GET/HEAD only`, `no write actions`, `no holdout expansion`).
  - Added template `src/quant_eam/ui/templates/ia_coverage.html` and navigation entry in `src/quant_eam/ui/templates/base.html`.
  - Added regression test `tests/test_ui_ia_coverage_phase37.py` and extended smoke checks in `tests/test_ui_mvp.py`.
  - Acceptance passed:
    - `docker compose run --rm api pytest -q tests/test_ui_ia_coverage_phase37.py tests/test_ui_mvp.py` -> PASS (`6 passed, 48 warnings in 7.98s`).
    - `python3 scripts/check_docs_tree.py` -> PASS (`docs tree: OK`).
    - `python3 scripts/check_subagent_packet.py --phase-id phase_57` -> PASS (bootstrap success marker row recorded before real packet check).
  - SSOT writeback completed by orchestrator only: `G37.status_now=implemented`.
