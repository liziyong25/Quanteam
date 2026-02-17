# Phase-35: Prompt Studio (G11)

## 1) 目标（Goal）
- 完成 G11：落地 `/ui/prompts` 的 Prompt Studio，支持版本浏览、`publish vN+1`、`pin per job` 与审计链。

## 2) 背景（Background）
- SSOT 中 G11 仍为 planned。
- `autopilot_stop_condition_exceptions_v1` 对 G11 已预授权 `/ui/prompts` 范围内的 route/API 行为变化。

## 3) 范围（Scope）
### In Scope
- 新增 `/ui/prompts`、`/ui/prompts/{agent_id}`、publish/pin POST 路由。
- 新增 Prompt Studio UI 模板与必要样式。
- publish 默认写 `artifacts/prompt_overrides/**`。
- pin 事件写 `jobs/<job_id>/outputs/prompts/**`，并写全局审计 `artifacts/audit/prompt_events.jsonl`。
- 新增 `tests/test_prompt_studio_g11.py` 并回归 `tests/test_ui_mvp.py`。

### Out of Scope
- 修改 `contracts/**`、`policies/**`。
- 修改 agents/orchestrator 的运行时 prompt 消费逻辑。

## 4) 任务卡（Task Card）
### Single Deliverable
- `G11` from `planned` to `implemented`.

### Allowed Paths
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/**`
- `src/quant_eam/ui/static/**`
- `tests/test_prompt_studio_g11.py`
- `docs/08_phases/00_skeleton/phase_35_prompt_studio_g11.md`
- `docs/12_workflows/skeleton_ssot_v1.yaml`
- `artifacts/prompt_overrides/**`
- `artifacts/audit/prompt_events.jsonl`
- `artifacts/subagent_control/phase_35/**`

### Stop Conditions
- 触发 `autopilot_stop_conditions_v1` 任一项即暂停并上报用户；
- 但 G11 允许在 exception 白名单内进行 `/ui/prompts` 路由/API 行为变更。

## 5) Subagent Control Packet
- `phase_id`: `phase_35`
- `packet_root`: `artifacts/subagent_control/phase_35/`

## 6) 验收标准（Acceptance Criteria / DoD）
- `docker compose run --rm api pytest -q tests/test_prompt_studio_g11.py tests/test_ui_mvp.py`
- `python3 scripts/check_docs_tree.py`
- `python3 scripts/check_subagent_packet.py --phase-id phase_35`

## 7) 预期产物（Artifacts）
- Prompt Studio UI 路由与页面可用。
- publish vN+1/pin per job 审计链可验证。
- `G11.status_now=implemented`。
- `prompt_studio_v1.status_now=implemented`。

## 8) 完成记录（Execution Log）
- Start Date: 2026-02-11
- End Date: 2026-02-11
- Notes:
  - Published by orchestrator before execution.
  - Acceptance:
    - `docker compose run --rm api pytest -q tests/test_prompt_studio_g11.py tests/test_ui_mvp.py` -> pass
    - `python3 scripts/check_docs_tree.py` -> pass
    - `python3 scripts/check_subagent_packet.py --phase-id phase_35` -> pass
  - G11 exception scope used only for `/ui/prompts` route/API behavior changes.
