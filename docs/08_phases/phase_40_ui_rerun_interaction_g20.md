# Phase-40: UI Rerun(agent_id) Interaction (G20)

## 1) 目标（Goal）
- 完成 G20：提供 `Rerun(agent_id)` 交互，记录可审计 rerun 事件与证据，并执行所选 agent 的重跑。

## 2) 背景（Background）
- 当前 UI/API 尚未提供显式 rerun 操作。
- 受 `g20_rerun_route_scope` 预授权，本 phase 允许在 `/ui/jobs` 与 `/jobs` 路由范围内实现 rerun 行为。

## 3) 范围（Scope）
### In Scope
- 新增 API：`POST /jobs/{job_id}/rerun`
- 新增 UI：`POST /ui/jobs/{job_id}/rerun` 与 job 页面 rerun 控件
- 追加 rerun 证据：
  - `jobs/<job_id>/outputs/reruns/rerun_log.jsonl`（append-only）
  - `jobs/<job_id>/outputs/reruns/rerun_state.json`（派生态）
  - `jobs/<job_id>/outputs/agents/<agent_dir>/reruns/<rerun_id>/agent_run.json`
- 读取 job 级 prompt pin 状态（若存在）并在 rerun 时带入 prompt 版本上下文。

### Out of Scope
- 修改 `contracts/**` 或 `policies/**`
- 扩展 holdout 可见性

## 4) 任务卡（Task Card）
### Single Deliverable
- `G20` from `planned` to `implemented`.

### Allowed Paths
- `src/quant_eam/api/jobs_api.py`
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/job.html`
- `src/quant_eam/ui/static/**`
- `tests/test_rerun_agent_phase20.py`
- `docs/08_phases/phase_40_ui_rerun_interaction_g20.md`
- `docs/12_workflows/agents_ui_ssot_v1.yaml`
- `artifacts/subagent_control/phase_40/**`

### Stop Conditions
- 触发 `autopilot_stop_conditions_v1` 任一项即暂停并上报用户（已配置 exception 的范围内除外）。

## 5) Subagent Control Packet
- `phase_id`: `phase_40`
- `packet_root`: `artifacts/subagent_control/phase_40/`
- evidence_policy: `hardened`
- external_noise_paths: enabled（忽略已知外部噪音路径）

## 6) 验收标准（Acceptance Criteria / DoD）
- `docker compose run --rm api pytest -q tests/test_rerun_agent_phase20.py tests/test_ui_mvp.py`
- `python3 scripts/check_docs_tree.py`
- `python3 scripts/check_subagent_packet.py --phase-id phase_40`

## 7) 预期产物（Artifacts）
- `jobs/<job_id>/events.jsonl`（rerun request 相关事件）
- `jobs/<job_id>/outputs/reruns/rerun_log.jsonl`
- `jobs/<job_id>/outputs/reruns/rerun_state.json`
- `jobs/<job_id>/outputs/agents/<agent_dir>/reruns/<rerun_id>/agent_run.json`

## 8) 完成记录（Execution Log）
- Start Date: 2026-02-11
- End Date: 2026-02-11
- Notes:
  - Published by orchestrator before execution.
  - Acceptance:
    - `docker compose run --rm api pytest -q tests/test_rerun_agent_phase20.py tests/test_ui_mvp.py` -> pass
    - `python3 scripts/check_docs_tree.py` -> pass
    - `python3 scripts/check_subagent_packet.py --phase-id phase_40` -> pass
  - Rerun evidence is append-only under `jobs/<job_id>/outputs/reruns/` and preserves prior artifacts immutability.
