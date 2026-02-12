# Phase-56: Playbook Phase Matrix Read-Only Page (G36)

## 1) 目标（Goal）
- 完成 G36：交付 `/ui/playbook-phases` 只读页面，展示 Implementation Phases Playbook 相位矩阵与 SSOT 映射证据。

## 2) 背景（Background）
- Implementation Phases Playbook 第 3 节定义施工 phase 列表与顺序。
- 无人值守模式需要通过 UI 审阅 phase 规划与当前 SSOT 状态映射，避免流程漂移。

## 3) 范围（Scope）
### In Scope
- 新增 `/ui/playbook-phases` 只读路由和模板渲染。
- 从 `docs/00_overview/Quant‑EAM Implementation Phases Playbook.md` 提取 phase 列表并展示。
- 映射 SSOT `phase_dispatch_plan_v2` / `goal_checklist` 状态生成只读矩阵。
- 增补 G36 回归测试覆盖可访问性、只读语义与关键映射字段展示。

### Out of Scope
- 修改 `contracts/**`。
- 修改 `policies/**`。
- 扩展 holdout 可见性。
- 新增写接口或修改非 G36 范围路由行为。

## 4) 任务卡（Task Card）
### Single Deliverable
- `G36` from `planned` to `implemented`.

### Allowed Paths
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/**`
- `src/quant_eam/ui/static/**`
- `tests/test_ui_mvp.py`
- `tests/test_ui_playbook_phases_phase36.py`
- `docs/08_phases/phase_56_*.md`
- `docs/12_workflows/agents_ui_ssot_v1.yaml`
- `artifacts/subagent_control/phase_56/**`

### Stop Conditions
- 触发 `autopilot_stop_conditions_v1` 任一项即暂停（仅 G36 exception 白名单范围内放行）。
- Subagent 禁止修改 `docs/12_workflows/agents_ui_ssot_v1.yaml`；仅主控在全部验收通过后回写 `G36.status_now=implemented`。

## 5) Subagent Control Packet
- `phase_id`: `phase_56`
- `packet_root`: `artifacts/subagent_control/phase_56/`
- `evidence_policy`: `hardened`

## 6) 验收标准（Acceptance Criteria / DoD）
- `docker compose run --rm api pytest -q tests/test_ui_playbook_phases_phase36.py tests/test_ui_mvp.py`
- `python3 scripts/check_docs_tree.py`
- `python3 scripts/check_subagent_packet.py --phase-id phase_56`

## 7) 预期产物（Artifacts）
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/playbook_phases.html`
- `tests/test_ui_playbook_phases_phase36.py`
- `tests/test_ui_mvp.py`
- `artifacts/subagent_control/phase_56/task_card.yaml`
- `artifacts/subagent_control/phase_56/executor_report.yaml`
- `artifacts/subagent_control/phase_56/validator_report.yaml`

## 8) 完成记录（Execution Log）
- Start Date: 2026-02-12
- End Date: 2026-02-12
- Notes:
  - Implemented `/ui/playbook-phases` as GET/HEAD-only evidence route with playbook section-3 extraction and SSOT `phase_dispatch_plan_v2` + `goal_checklist` status mapping matrix.
  - Added template `src/quant_eam/ui/templates/playbook_phases.html` and navigation entry in `src/quant_eam/ui/templates/base.html`; page includes explicit governance boundary (`GET/HEAD only`, `no write actions`, `no holdout expansion`).
  - Added regression coverage in `tests/test_ui_playbook_phases_phase36.py` and updated `tests/test_ui_mvp.py` to include the new page.
  - Acceptance passed:
    - `docker compose run --rm api pytest -q tests/test_ui_playbook_phases_phase36.py tests/test_ui_mvp.py` -> passed (`6 passed, 48 warnings`).
    - `python3 scripts/check_docs_tree.py` -> passed (`docs tree: OK`).
    - `python3 scripts/check_subagent_packet.py --phase-id phase_56` -> bootstrap success marker logged first, then real packet check executed and passed.
  - SSOT writeback completed by orchestrator only: `G36.status_now=implemented`.
