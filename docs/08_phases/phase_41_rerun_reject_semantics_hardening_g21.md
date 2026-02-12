# Phase-41: Rerun/Reject Semantics Hardening (G21)

## 1) 目标（Goal）
- 完成 G21：修复 `Rerun(agent_id)` 与 `Reject(step=...)` 的语义冲突，保证流程与预算语义一致。

## 2) 背景（Background）
- 现状存在两类风险：
  - rerun 事件可能被当作 spawn 计数，影响 budget 行为。
  - job 仍处于 waiting checkpoint 时，rerun 后 reject 可能被错误拒绝。
- 本 phase 通过 `g21_rerun_reject_semantics_scope` 预授权在 `/ui/jobs` 与 `/jobs` 路由范围内修复。

## 3) 范围（Scope）
### In Scope
- 修正 rerun 事件/计数语义，确保不消耗 spawn budget。
- 修正 reject 的 waiting step 判断，使其与 UI waiting 语义一致。
- 补充回归测试覆盖：
  - `rerun -> reject` 连续操作可用。
  - rerun 不影响 spawn budget 计数。

### Out of Scope
- 修改 `contracts/**` 或 `policies/**`
- 扩展 holdout 可见性

## 4) 任务卡（Task Card）
### Single Deliverable
- `G21` from `planned` to `implemented`.

### Allowed Paths
- `src/quant_eam/api/jobs_api.py`
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/jobstore/store.py`
- `src/quant_eam/ui/templates/job.html`
- `src/quant_eam/ui/static/**`
- `tests/test_reject_step_phase19.py`
- `tests/test_rerun_agent_phase20.py`
- `tests/test_ui_mvp.py`
- `docs/08_phases/phase_41_rerun_reject_semantics_hardening_g21.md`
- `docs/12_workflows/agents_ui_ssot_v1.yaml`
- `artifacts/subagent_control/phase_41/**`

### Stop Conditions
- 触发 `autopilot_stop_conditions_v1` 任一项即暂停并上报用户（已配置 exception 的范围内除外）。

## 5) Subagent Control Packet
- `phase_id`: `phase_41`
- `packet_root`: `artifacts/subagent_control/phase_41/`
- evidence_policy: `hardened`
- external_noise_paths: enabled（忽略已知外部噪音路径）

## 6) 验收标准（Acceptance Criteria / DoD）
- `docker compose run --rm api pytest -q tests/test_reject_step_phase19.py tests/test_rerun_agent_phase20.py tests/test_ui_mvp.py`
- `python3 scripts/check_docs_tree.py`
- `python3 scripts/check_subagent_packet.py --phase-id phase_41`

## 7) 预期产物（Artifacts）
- `jobs/<job_id>/events.jsonl`（rerun/reject 相关事件）
- `jobs/<job_id>/outputs/reruns/rerun_log.jsonl`
- `jobs/<job_id>/outputs/rejections/reject_log.jsonl`
- `artifacts/subagent_control/phase_41/task_card.yaml`
- `artifacts/subagent_control/phase_41/executor_report.yaml`
- `artifacts/subagent_control/phase_41/validator_report.yaml`

## 8) 完成记录（Execution Log）
- Start Date: 2026-02-11
- End Date: 2026-02-11
- Notes:
  - Published by orchestrator before subagent execution.
  - Hardened `reject` waiting-step resolver: rerun append-only events no longer block `reject(step=current_waiting_step)`.
  - Spawn budget counting now excludes rerun audit events (`SPAWNED` with `outputs.action=rerun_requested`).
  - Added regression tests for `rerun -> reject` and `rerun` budget isolation.
