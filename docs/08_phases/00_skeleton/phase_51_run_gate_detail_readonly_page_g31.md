# Phase-51: Run Gate Detail Read-Only Page (G31)

## 1) 目标（Goal）
- 完成 G31：交付 `/ui/runs/<run_id>/gates` 只读页面，提供逐 gate 的 pass/fail、阈值、状态与证据引用，支持 UI 黑盒审阅。

## 2) 背景（Background）
- Whole View Framework 要求用户在 UI 完成 Gate 证据审阅，而不依赖源码分析。
- 现有 `/ui/runs/<run_id>` 已展示运行摘要；G31 需补齐专门 Gate 详情页，强化证据阅读体验与治理边界。

## 3) 范围（Scope）
### In Scope
- 增加 `/ui/runs/<run_id>/gates` 只读路由和模板渲染。
- 展示 `gate_results.json` 的 gate 列表、overall 状态与 holdout 摘要（仅最小摘要）。
- 增补 G31 回归测试覆盖可访问性、只读语义与证据字段展示。

### Out of Scope
- 修改 `contracts/**`。
- 修改 `policies/**`。
- 扩展 holdout 可见性。
- 新增写接口或修改无关 API/UI 行为。

## 4) 任务卡（Task Card）
### Single Deliverable
- `G31` from `planned` to `implemented`.

### Allowed Paths
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/**`
- `src/quant_eam/ui/static/**`
- `tests/test_ui_mvp.py`
- `tests/test_ui_run_gates_phase31.py`
- `docs/08_phases/00_skeleton/phase_51_run_gate_detail_readonly_page_g31.md`
- `docs/12_workflows/skeleton_ssot_v1.yaml`
- `artifacts/subagent_control/phase_51/**`

### Stop Conditions
- 触发 `autopilot_stop_conditions_v1` 任一项即暂停（仅 G31 exception 白名单范围内放行）。
- Subagent 禁止修改 `docs/12_workflows/skeleton_ssot_v1.yaml`；仅主控在全部验收通过后回写 `G31.status_now=implemented`。

## 5) Subagent Control Packet
- `phase_id`: `phase_51`
- `packet_root`: `artifacts/subagent_control/phase_51/`
- `evidence_policy`: `hardened`

## 6) 验收标准（Acceptance Criteria / DoD）
- `docker compose run --rm api pytest -q tests/test_ui_run_gates_phase31.py tests/test_ui_mvp.py`
- `python3 scripts/check_docs_tree.py`
- `python3 scripts/check_subagent_packet.py --phase-id phase_51`

## 7) 预期产物（Artifacts）
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/run_gates.html`
- `tests/test_ui_run_gates_phase31.py`
- `tests/test_ui_mvp.py`
- `artifacts/subagent_control/phase_51/task_card.yaml`
- `artifacts/subagent_control/phase_51/executor_report.yaml`
- `artifacts/subagent_control/phase_51/validator_report.yaml`

## 8) 完成记录（Execution Log）
- Start Date: 2026-02-11
- End Date: 2026-02-11
- Notes:
  - Published by orchestrator before subagent execution.
  - Task card enforces hardened evidence and G31 exception-scoped allowed paths.
  - Added read-only route/template: `/ui/runs/<run_id>/gates` with per-gate status/thresholds/evidence references.
  - Added G31 UI regression coverage in `tests/test_ui_run_gates_phase31.py` and linked from `/ui/runs/<run_id>`.
  - Holdout visibility remains minimal summary only (`pass` + `summary`).
  - Acceptance passed:
    - `docker compose run --rm api pytest -q tests/test_ui_run_gates_phase31.py tests/test_ui_mvp.py`
    - `python3 scripts/check_docs_tree.py`
    - `python3 scripts/check_subagent_packet.py --phase-id phase_51`
  - SSOT writeback completed by orchestrator only: `G31.status_now=implemented`.
