# Phase-73: Whole View Contracts Principles and Trace Boundary Evidence Page (G53)

## 1) 目标（Goal）
- 完成 G53：交付 `/ui/contracts-principles` 只读页面，展示《Quant‑EAM Whole View Framework》section 5 的 contracts 体系原则与 trace 计划/结果边界证据。

## 2) 背景（Background）
- Whole View section 5 定义了 contracts 体系的核心原则（版本化、静态可分析、对齐显式化、trace 计划/结果分离）。
- 该原则需要在 UI 中只读可审阅，作为后续自动化研发过程的治理证据。

## 3) 范围（Scope）
### In Scope
- 新增 `/ui/contracts-principles` 只读路由与模板渲染。
- 从 `Quant‑EAM Whole View Framework.md` section 5 提取 contracts 原则与 trace 计划/结果边界证据。
- 增补 G53 回归测试覆盖只读语义、核心原则展示与可访问性。

### Out of Scope
- 修改 `contracts/**`。
- 修改 `policies/**`。
- 扩展 holdout 可见性。
- 新增写接口或修改非 G53 范围路由行为。

## 4) 任务卡（Task Card）
### Single Deliverable
- `G53` from `planned` to `implemented`.

### Allowed Paths
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/**`
- `src/quant_eam/ui/static/**`
- `tests/test_ui_mvp.py`
- `tests/test_ui_contracts_principles_phase53.py`
- `docs/08_phases/00_skeleton/phase_73_*.md`
- `docs/12_workflows/skeleton_ssot_v1.yaml`
- `artifacts/subagent_control/phase_73/**`

### Stop Conditions
- 触发 `autopilot_stop_conditions_v1` 任一项即暂停（仅 G53 exception 白名单范围内放行）。
- Subagent 禁止修改 `docs/12_workflows/skeleton_ssot_v1.yaml`；仅主控在全部验收通过后回写 `G53.status_now=implemented`。

## 5) Subagent Control Packet
- `phase_id`: `phase_73`
- `packet_root`: `artifacts/subagent_control/phase_73/`
- `evidence_policy`: `hardened`

## 6) 验收标准（Acceptance Criteria / DoD）
- `docker compose run --rm api pytest -q tests/test_ui_contracts_principles_phase53.py tests/test_ui_mvp.py`
- `python3 scripts/check_docs_tree.py`
- `python3 scripts/check_subagent_packet.py --phase-id phase_73`

## 7) 预期产物（Artifacts）
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/contracts_principles.html`
- `tests/test_ui_contracts_principles_phase53.py`
- `tests/test_ui_mvp.py`
- `artifacts/subagent_control/phase_73/task_card.yaml`
- `artifacts/subagent_control/phase_73/executor_report.yaml`
- `artifacts/subagent_control/phase_73/validator_report.yaml`

## 8) 完成记录（Execution Log）
- Start Date: 2026-02-12
- End Date: 2026-02-12
- Notes:
  - Published by orchestrator before subagent execution.
  - Task card enforces hardened evidence and G53 exception-scoped allowed paths.
  - Implemented `/ui/contracts-principles` as a read-only evidence page with section-5-only extraction from `Quant‑EAM Whole View Framework.md` (contracts-system principles + trace plan/result boundary note + 5.1 required contracts).
  - Added/updated regression coverage: `tests/test_ui_contracts_principles_phase53.py` and `tests/test_ui_mvp.py` for route availability, section-5 evidence rendering, and no-write semantics.
  - Acceptance outcome: required pytest/docs/packet commands passed.
  - Subagent packet remains pre-writeback: `validator_report.checks[name=ssot_updated].pass=false`; SSOT writeback remains orchestrator-owned.
  - Orchestrator finalized writeback: `docs/12_workflows/skeleton_ssot_v1.yaml` updated to `G53.status_now=implemented`; `validator_report.yaml` promoted to final pass state.
