# Phase-75: Whole View Codex Role Boundary Evidence Page (G55)

## 1) 目标（Goal）
- 完成 G55：交付 `/ui/codex-role-boundary` 只读页面，展示《Quant‑EAM Whole View Framework》section 7 的 Codex 角色定位与治理边界证据。

## 2) 背景（Background）
- Whole View section 7 明确 Codex CLI 是探索者与工具工，不是裁判；裁决必须由确定性 Gate 体系给出。
- 该边界需要在 UI 中只读可审阅，避免无人值守执行中越权裁决。

## 3) 范围（Scope）
### In Scope
- 新增 `/ui/codex-role-boundary` 只读路由与模板渲染。
- 从 `Quant‑EAM Whole View Framework.md` section 7 提取 Codex 角色定位、临时诊断与晋升治理边界证据。
- 增补 G55 回归测试覆盖只读语义、边界条目展示与可访问性。

### Out of Scope
- 修改 `contracts/**`。
- 修改 `policies/**`。
- 扩展 holdout 可见性。
- 新增写接口或修改非 G55 范围路由行为。

## 4) 任务卡（Task Card）
### Single Deliverable
- `G55` from `planned` to `implemented`.

### Allowed Paths
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/**`
- `src/quant_eam/ui/static/**`
- `tests/test_ui_mvp.py`
- `tests/test_ui_codex_role_boundary_phase55.py`
- `docs/08_phases/00_skeleton/phase_75_*.md`
- `docs/12_workflows/skeleton_ssot_v1.yaml`
- `artifacts/subagent_control/phase_75/**`

### Stop Conditions
- 触发 `autopilot_stop_conditions_v1` 任一项即暂停（仅 G55 exception 白名单范围内放行）。
- Subagent 禁止修改 `docs/12_workflows/skeleton_ssot_v1.yaml`；仅主控在全部验收通过后回写 `G55.status_now=implemented`。

## 5) Subagent Control Packet
- `phase_id`: `phase_75`
- `packet_root`: `artifacts/subagent_control/phase_75/`
- `evidence_policy`: `hardened`

## 6) 验收标准（Acceptance Criteria / DoD）
- `docker compose run --rm api pytest -q tests/test_ui_codex_role_boundary_phase55.py tests/test_ui_mvp.py`
- `python3 scripts/check_docs_tree.py`
- `python3 scripts/check_subagent_packet.py --phase-id phase_75`

## 7) 预期产物（Artifacts）
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/codex_role_boundary.html`
- `tests/test_ui_codex_role_boundary_phase55.py`
- `tests/test_ui_mvp.py`
- `artifacts/subagent_control/phase_75/task_card.yaml`
- `artifacts/subagent_control/phase_75/executor_report.yaml`
- `artifacts/subagent_control/phase_75/validator_report.yaml`

## 8) 完成记录（Execution Log）
- Start Date: 2026-02-12
- End Date: 2026-02-12
- Notes:
  - Published by orchestrator before subagent execution.
  - Task card enforces hardened evidence and G55 exception-scoped allowed paths.
  - Subagent implemented `GET/HEAD`-only route `/ui/codex-role-boundary` in `src/quant_eam/api/ui_routes.py`, with read-only template `src/quant_eam/ui/templates/codex_role_boundary.html`.
  - Evidence rendering is sourced only from root `Quant‑EAM Whole View Framework.md` section `7. Codex CLI 的定位：探索者 + 工具工，不是裁判` (including `7.1` ephemeral diagnostics and `7.2` promote-to-gate governance rows).
  - Added regression coverage in `tests/test_ui_codex_role_boundary_phase55.py` and extended `tests/test_ui_mvp.py` smoke checks for `/ui/codex-role-boundary`.
  - Governance boundary preserved on page render: `GET/HEAD only`, `no write actions`, and section-7-only evidence extraction with no write controls.
  - Acceptance outcome: required pytest/docs/packet commands passed.
  - Subagent packet remains pre-writeback: `validator_report.checks[name=ssot_updated].pass=false`; SSOT writeback remains orchestrator-owned.
  - Orchestrator finalized writeback: `docs/12_workflows/skeleton_ssot_v1.yaml` updated to `G55.status_now=implemented`; `validator_report.yaml` promoted to final pass state.
