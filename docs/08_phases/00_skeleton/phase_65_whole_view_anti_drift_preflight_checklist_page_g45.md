# Phase-65: Whole View Anti-Drift Preflight Checklist Page (G45)

## 1) 目标（Goal）
- 完成 G45：交付 `/ui/preflight-checklist` 只读页面，展示 Whole View section 10 “不跑偏”检查清单作为发布前治理证据。

## 2) 背景（Background）
- Whole View section 10 定义了每次扩展功能前必须核对的治理清单（contracts/policies/dossier/gates/holdout/budget/tests/docs）。
- 在无人值守主控链路中，该清单需要在 UI 可见并可审阅，避免实现偏离治理边界。

## 3) 范围（Scope）
### In Scope
- 新增 `/ui/preflight-checklist` 只读路由与模板渲染。
- 从 Whole View section 10 提取并展示 anti-drift preflight checklist。
- 增补 G45 回归测试，覆盖只读语义、关键条目与可访问性。

### Out of Scope
- 修改 `contracts/**`。
- 修改 `policies/**`。
- 扩展 holdout 可见性。
- 新增写接口或修改非 G45 范围路由行为。

## 4) 任务卡（Task Card）
### Single Deliverable
- `G45` from `planned` to `implemented`.

### Allowed Paths
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/**`
- `src/quant_eam/ui/static/**`
- `tests/test_ui_mvp.py`
- `tests/test_ui_preflight_checklist_phase45.py`
- `docs/08_phases/00_skeleton/phase_65_*.md`
- `docs/12_workflows/skeleton_ssot_v1.yaml`
- `artifacts/subagent_control/phase_65/**`

### Stop Conditions
- 触发 `autopilot_stop_conditions_v1` 任一项即暂停（仅 G45 exception 白名单范围内放行）。
- Subagent 禁止修改 `docs/12_workflows/skeleton_ssot_v1.yaml`；仅主控在全部验收通过后回写 `G45.status_now=implemented`。

## 5) Subagent Control Packet
- `phase_id`: `phase_65`
- `packet_root`: `artifacts/subagent_control/phase_65/`
- `evidence_policy`: `hardened`

## 6) 验收标准（Acceptance Criteria / DoD）
- `docker compose run --rm api pytest -q tests/test_ui_preflight_checklist_phase45.py tests/test_ui_mvp.py`
- `python3 scripts/check_docs_tree.py`
- `python3 scripts/check_subagent_packet.py --phase-id phase_65`

## 7) 预期产物（Artifacts）
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/preflight_checklist.html`
- `tests/test_ui_preflight_checklist_phase45.py`
- `tests/test_ui_mvp.py`
- `artifacts/subagent_control/phase_65/task_card.yaml`
- `artifacts/subagent_control/phase_65/executor_report.yaml`
- `artifacts/subagent_control/phase_65/validator_report.yaml`

## 8) 完成记录（Execution Log）
- Start Date: 2026-02-12
- End Date: 2026-02-12
- Notes:
  - Published by orchestrator before subagent execution.
  - Task card enforces hardened evidence and G45 exception-scoped allowed paths.
  - Subagent implemented G45 in scope: added `/ui/preflight-checklist` GET/HEAD route, Whole View section-10 checklist extraction context, and read-only template `src/quant_eam/ui/templates/preflight_checklist.html`.
  - Added regression coverage in `tests/test_ui_preflight_checklist_phase45.py` and extended `tests/test_ui_mvp.py` smoke checks for `/ui/preflight-checklist`.
  - Acceptance outcome: `docker compose run --rm api pytest -q tests/test_ui_preflight_checklist_phase45.py tests/test_ui_mvp.py` passed.
  - Acceptance outcome: `python3 scripts/check_docs_tree.py` passed.
  - Acceptance outcome: `python3 scripts/check_subagent_packet.py --phase-id phase_65` passed.
  - Orchestrator writeback completed: `docs/12_workflows/skeleton_ssot_v1.yaml` updated with `G45.status_now=implemented`; validator finalized to `status=pass`.
