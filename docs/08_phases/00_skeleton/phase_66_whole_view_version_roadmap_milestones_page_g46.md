# Phase-66: Whole View Version Roadmap Milestones Page (G46)

## 1) 目标（Goal）
- 完成 G46：交付 `/ui/version-roadmap` 只读页面，展示 Whole View section 11 的 v0.4/v0.5/v0.6 版本路线里程碑作为治理证据。

## 2) 背景（Background）
- Whole View section 11 给出了版本路线建议（v0.4/v0.5/v0.6），用于约束阶段建设节奏。
- 无人值守主控执行时，需要在 UI 中持续呈现版本路线与当前实现状态映射，避免路线漂移。

## 3) 范围（Scope）
### In Scope
- 新增 `/ui/version-roadmap` 只读路由与模板渲染。
- 从 Whole View section 11 提取并展示版本里程碑信息。
- 增补 G46 回归测试覆盖只读语义、关键里程碑展示与可访问性。

### Out of Scope
- 修改 `contracts/**`。
- 修改 `policies/**`。
- 扩展 holdout 可见性。
- 新增写接口或修改非 G46 范围路由行为。

## 4) 任务卡（Task Card）
### Single Deliverable
- `G46` from `planned` to `implemented`.

### Allowed Paths
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/**`
- `src/quant_eam/ui/static/**`
- `tests/test_ui_mvp.py`
- `tests/test_ui_version_roadmap_phase46.py`
- `docs/08_phases/00_skeleton/phase_66_*.md`
- `docs/12_workflows/skeleton_ssot_v1.yaml`
- `artifacts/subagent_control/phase_66/**`

### Stop Conditions
- 触发 `autopilot_stop_conditions_v1` 任一项即暂停（仅 G46 exception 白名单范围内放行）。
- Subagent 禁止修改 `docs/12_workflows/skeleton_ssot_v1.yaml`；仅主控在全部验收通过后回写 `G46.status_now=implemented`。

## 5) Subagent Control Packet
- `phase_id`: `phase_66`
- `packet_root`: `artifacts/subagent_control/phase_66/`
- `evidence_policy`: `hardened`

## 6) 验收标准（Acceptance Criteria / DoD）
- `docker compose run --rm api pytest -q tests/test_ui_version_roadmap_phase46.py tests/test_ui_mvp.py`
- `python3 scripts/check_docs_tree.py`
- `python3 scripts/check_subagent_packet.py --phase-id phase_66`

## 7) 预期产物（Artifacts）
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/version_roadmap.html`
- `tests/test_ui_version_roadmap_phase46.py`
- `tests/test_ui_mvp.py`
- `artifacts/subagent_control/phase_66/task_card.yaml`
- `artifacts/subagent_control/phase_66/executor_report.yaml`
- `artifacts/subagent_control/phase_66/validator_report.yaml`

## 8) 完成记录（Execution Log）
- Start Date: 2026-02-12
- End Date: 2026-02-12
- Notes:
  - Published by orchestrator before subagent execution.
  - Task card enforces hardened evidence and G46 exception-scoped allowed paths.
  - Implementation: added read-only `/ui/version-roadmap` route + `version_roadmap.html`, extracting Whole View section 11 roadmap milestones (`v0.4`/`v0.5`/`v0.6`) as governance evidence; no write controls added.
  - Tests: added `tests/test_ui_version_roadmap_phase46.py` and extended `tests/test_ui_mvp.py` coverage for `/ui/version-roadmap`.
  - Acceptance outcome: `docker compose run --rm api pytest -q tests/test_ui_version_roadmap_phase46.py tests/test_ui_mvp.py` passed.
  - Acceptance outcome: `python3 scripts/check_docs_tree.py` passed.
  - Acceptance outcome: `python3 scripts/check_subagent_packet.py --phase-id phase_66` passed.
  - Orchestrator writeback completed: `docs/12_workflows/skeleton_ssot_v1.yaml` updated with `G46.status_now=implemented`; validator finalized to `status=pass`.
