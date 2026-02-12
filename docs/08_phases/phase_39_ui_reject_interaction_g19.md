# Phase-39: UI Reject(step=...) Interaction (G19)

## 1) 目标（Goal）
- 完成 G19：提供 `Reject(step=...)` 交互，写入可审计 reject 证据，并回到配置的 fallback 审批步。

## 2) 背景（Background）
- 当前 UI/API 仅支持 `Approve(step=...)`，缺少 reject 交互与 reject 证据链。
- 受 `g19_reject_route_scope` 预授权，本 phase 允许在 `/ui/jobs` 与 `/jobs` 相关路由内落地行为变更。

## 3) 范围（Scope）
### In Scope
- 新增 API：`POST /jobs/{job_id}/reject`
- 新增 UI：`POST /ui/jobs/{job_id}/reject` 与 job 页面 reject 表单
- 追加 reject 证据：
  - `jobs/<job_id>/outputs/rejections/reject_log.jsonl`（append-only）
  - `jobs/<job_id>/outputs/rejections/reject_state.json`（派生态）
- 新增测试覆盖 reject 交互、鉴权与证据落盘。

### Out of Scope
- 修改 `contracts/**` 或 `policies/**`
- 修改 orchestrator kernel 的运行核心逻辑

## 4) 任务卡（Task Card）
### Single Deliverable
- `G19` from `planned` to `implemented`.

### Allowed Paths
- `src/quant_eam/api/jobs_api.py`
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/job.html`
- `src/quant_eam/ui/static/**`
- `tests/test_reject_step_phase19.py`
- `docs/08_phases/phase_39_ui_reject_interaction_g19.md`
- `docs/12_workflows/agents_ui_ssot_v1.yaml`
- `artifacts/subagent_control/phase_39/**`

### Stop Conditions
- 触发 `autopilot_stop_conditions_v1` 任一项即暂停并上报用户（已配置 exception 的范围内除外）。

## 5) Subagent Control Packet
- `phase_id`: `phase_39`
- `packet_root`: `artifacts/subagent_control/phase_39/`
- evidence_policy: `hardened`
- external_noise_paths: enabled（忽略已知外部噪音路径）

## 6) 验收标准（Acceptance Criteria / DoD）
- `docker compose run --rm api pytest -q tests/test_reject_step_phase19.py tests/test_ui_mvp.py`
- `python3 scripts/check_docs_tree.py`
- `python3 scripts/check_subagent_packet.py --phase-id phase_39`

## 7) 预期产物（Artifacts）
- `jobs/<job_id>/events.jsonl`（reject 相关审批流事件）
- `jobs/<job_id>/outputs/rejections/reject_log.jsonl`
- `jobs/<job_id>/outputs/rejections/reject_state.json`

## 8) 完成记录（Execution Log）
- Start Date: 2026-02-11
- End Date: 2026-02-11
- Notes:
  - Published by orchestrator before execution.
  - Acceptance:
    - `docker compose run --rm api pytest -q tests/test_reject_step_phase19.py tests/test_ui_mvp.py` -> pass
    - `python3 scripts/check_docs_tree.py` -> pass
    - `python3 scripts/check_subagent_packet.py --phase-id phase_39` -> pass
  - Reject evidence is append-only under `jobs/<job_id>/outputs/rejections/` and does not mutate prior dossier/registry artifacts.
