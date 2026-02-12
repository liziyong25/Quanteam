# Phase-69: Whole View Hard Constraints Governance Evidence Page (G49)

## 1) 目标（Goal）
- 完成 G49：交付 `/ui/hard-constraints` 只读页面，展示《Quant‑EAM Whole View Framework》section 1 的系统硬约束治理证据。

## 2) 背景（Background）
- Whole View section 1 列出了无人值守执行不可突破的硬约束（policies 只读、裁决边界、holdout 防污染、测试覆盖、预算停止条件）。
- 这些约束需要可视化并持续审阅，作为主控执行的治理护栏。

## 3) 范围（Scope）
### In Scope
- 新增 `/ui/hard-constraints` 只读路由与模板渲染。
- 从 `Quant‑EAM Whole View Framework.md` section 1 提取硬约束证据。
- 增补 G49 回归测试覆盖只读语义、关键条目展示与可访问性。

### Out of Scope
- 修改 `contracts/**`。
- 修改 `policies/**`。
- 扩展 holdout 可见性。
- 新增写接口或修改非 G49 范围路由行为。

## 4) 任务卡（Task Card）
### Single Deliverable
- `G49` from `planned` to `implemented`.

### Allowed Paths
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/**`
- `src/quant_eam/ui/static/**`
- `tests/test_ui_mvp.py`
- `tests/test_ui_hard_constraints_phase49.py`
- `docs/08_phases/phase_69_*.md`
- `docs/12_workflows/agents_ui_ssot_v1.yaml`
- `artifacts/subagent_control/phase_69/**`

### Stop Conditions
- 触发 `autopilot_stop_conditions_v1` 任一项即暂停（仅 G49 exception 白名单范围内放行）。
- Subagent 禁止修改 `docs/12_workflows/agents_ui_ssot_v1.yaml`；仅主控在全部验收通过后回写 `G49.status_now=implemented`。

## 5) Subagent Control Packet
- `phase_id`: `phase_69`
- `packet_root`: `artifacts/subagent_control/phase_69/`
- `evidence_policy`: `hardened`

## 6) 验收标准（Acceptance Criteria / DoD）
- `docker compose run --rm api pytest -q tests/test_ui_hard_constraints_phase49.py tests/test_ui_mvp.py`
- `python3 scripts/check_docs_tree.py`
- `python3 scripts/check_subagent_packet.py --phase-id phase_69`

## 7) 预期产物（Artifacts）
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/hard_constraints.html`
- `tests/test_ui_hard_constraints_phase49.py`
- `tests/test_ui_mvp.py`
- `artifacts/subagent_control/phase_69/task_card.yaml`
- `artifacts/subagent_control/phase_69/executor_report.yaml`
- `artifacts/subagent_control/phase_69/validator_report.yaml`

## 8) 完成记录（Execution Log）
- Start Date: 2026-02-12
- End Date: 2026-02-12
- Notes:
  - Published by orchestrator before subagent execution.
  - Task card enforces hardened evidence and G49 exception-scoped allowed paths.

## 9) Implementation Notes (Subagent)
- Added read-only route `GET/HEAD /ui/hard-constraints` in `src/quant_eam/api/ui_routes.py`.
- Added scoped page context sourced only from root `Quant‑EAM Whole View Framework.md` section 1 hard constraints.
- Added read-only template `src/quant_eam/ui/templates/hard_constraints.html` with governance boundary indicators and section-1 evidence table.
- Added regression test `tests/test_ui_hard_constraints_phase49.py` and extended `tests/test_ui_mvp.py` smoke checks for `/ui/hard-constraints`.

## 10) Acceptance Notes
- Required acceptance commands executed successfully in subagent workspace and rerun by orchestrator:
  - `docker compose run --rm api pytest -q tests/test_ui_hard_constraints_phase49.py tests/test_ui_mvp.py`
  - `python3 scripts/check_docs_tree.py`
  - `python3 scripts/check_subagent_packet.py --phase-id phase_69`
- Acceptance run log updated at `artifacts/subagent_control/phase_69/acceptance_run_log.jsonl`.
- Subagent governance boundary preserved: `docs/12_workflows/agents_ui_ssot_v1.yaml` unchanged by subagent.
- Orchestrator writeback completed: `docs/12_workflows/agents_ui_ssot_v1.yaml` updated with `G49.status_now=implemented`; `artifacts/subagent_control/phase_69/validator_report.yaml` finalized to `status=pass`.
