# Phase-67: Whole View System Definition and Planes Evidence Page (G47)

## 1) 目标（Goal）
- 完成 G47：交付 `/ui/system-definition` 只读页面，展示《Quant‑EAM Whole View Framework》section 0/2 的系统定义与五平面架构证据。

## 2) 背景（Background）
- Whole View section 0 明确系统不是“策略工厂”，而是可审计经验资产系统。
- Whole View section 2 明确五个平面与职责边界，需要在 UI 可审阅呈现，防止后续实现偏离框架定义。

## 3) 范围（Scope）
### In Scope
- 新增 `/ui/system-definition` 只读路由与模板渲染。
- 从 `Quant‑EAM Whole View Framework.md` section 0/2 提取系统定义与五平面证据。
- 增补 G47 回归测试覆盖只读语义、关键字段展示与可访问性。

### Out of Scope
- 修改 `contracts/**`。
- 修改 `policies/**`。
- 扩展 holdout 可见性。
- 新增写接口或修改非 G47 范围路由行为。

## 4) 任务卡（Task Card）
### Single Deliverable
- `G47` from `planned` to `implemented`.

### Allowed Paths
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/**`
- `src/quant_eam/ui/static/**`
- `tests/test_ui_mvp.py`
- `tests/test_ui_system_definition_phase47.py`
- `docs/08_phases/00_skeleton/phase_67_*.md`
- `docs/12_workflows/skeleton_ssot_v1.yaml`
- `artifacts/subagent_control/phase_67/**`

### Stop Conditions
- 触发 `autopilot_stop_conditions_v1` 任一项即暂停（仅 G47 exception 白名单范围内放行）。
- Subagent 禁止修改 `docs/12_workflows/skeleton_ssot_v1.yaml`；仅主控在全部验收通过后回写 `G47.status_now=implemented`。

## 5) Subagent Control Packet
- `phase_id`: `phase_67`
- `packet_root`: `artifacts/subagent_control/phase_67/`
- `evidence_policy`: `hardened`

## 6) 验收标准（Acceptance Criteria / DoD）
- `docker compose run --rm api pytest -q tests/test_ui_system_definition_phase47.py tests/test_ui_mvp.py`
- `python3 scripts/check_docs_tree.py`
- `python3 scripts/check_subagent_packet.py --phase-id phase_67`

## 7) 预期产物（Artifacts）
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/system_definition.html`
- `tests/test_ui_system_definition_phase47.py`
- `tests/test_ui_mvp.py`
- `artifacts/subagent_control/phase_67/task_card.yaml`
- `artifacts/subagent_control/phase_67/executor_report.yaml`
- `artifacts/subagent_control/phase_67/validator_report.yaml`

## 8) 完成记录（Execution Log）
- Start Date: 2026-02-12
- End Date: 2026-02-12
- Notes:
  - Published by orchestrator before subagent execution.
  - Task card enforces hardened evidence and G47 exception-scoped allowed paths.
  - Subagent implemented G47 in scope: added read-only `/ui/system-definition` GET/HEAD route and `system_definition.html` template, extracting only root `Quant‑EAM Whole View Framework.md` section 0/2 evidence (system definition + five planes).
  - Added regression coverage in `tests/test_ui_system_definition_phase47.py` and extended `tests/test_ui_mvp.py` smoke checks for `/ui/system-definition`.
  - Acceptance outcome: `docker compose run --rm api pytest -q tests/test_ui_system_definition_phase47.py tests/test_ui_mvp.py` passed.
  - Acceptance outcome: `python3 scripts/check_docs_tree.py` passed.
  - Acceptance outcome: `python3 scripts/check_subagent_packet.py --phase-id phase_67` passed.
  - Orchestrator writeback completed: `docs/12_workflows/skeleton_ssot_v1.yaml` updated with `G47.status_now=implemented`; validator finalized to `status=pass`.
