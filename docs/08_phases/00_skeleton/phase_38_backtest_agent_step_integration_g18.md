# Phase-38: Backtest Agent Step Integration (G18)

## 1) 目标（Goal）
- 完成 G18：在 runspec 审批后接入 `backtest_agent_v1`，并在确定性 runner/gaterunner 产物上生成可审计 `run_link.json`。

## 2) 背景（Background）
- 当前流程已在 runspec 审批后执行 demo + trace_preview，但缺少 `outputs/agents/backtest/agent_run.json` 与 `outputs/run_link.json`。
- G18 需要把 backtest 过程桥接到确定性内核并保留可追踪链接证据。

## 3) 范围（Scope）
### In Scope
- 新增 `backtest_agent_v1`（harness 可执行）与 promptpack。
- orchestrator 在 runspec 审批后触发 backtest agent 证据写入。
- 在 run/gates 完成后写出 `outputs/run_link.json` 并写入 outputs index。
- 新增/更新 e2e 测试覆盖 backtest agent 证据与 run_link。

### Out of Scope
- 修改 contracts/** 或 policies/**。
- 修改 API route/schema。

## 4) 任务卡（Task Card）
### Single Deliverable
- `G18` from `planned` to `implemented`.

### Allowed Paths
- `src/quant_eam/orchestrator/workflow.py`
- `src/quant_eam/agents/harness.py`
- `src/quant_eam/agents/backtest_agent.py`
- `prompts/agents/backtest_agent_v1/**`
- `tests/test_agents_orchestrator_phase11_e2e.py`
- `tests/test_backtest_agent_phase18_e2e.py`
- `docs/08_phases/00_skeleton/phase_38_backtest_agent_step_integration_g18.md`
- `docs/12_workflows/skeleton_ssot_v1.yaml`
- `artifacts/subagent_control/phase_38/**`

### Stop Conditions
- 触发 `autopilot_stop_conditions_v1` 任一项即暂停并上报用户。

## 5) Subagent Control Packet
- `phase_id`: `phase_38`
- `packet_root`: `artifacts/subagent_control/phase_38/`
- evidence_policy: `hardened`
- external_noise_paths: `WBData/**`

## 6) 验收标准（Acceptance Criteria / DoD）
- `docker compose run --rm api pytest -q tests/test_agents_orchestrator_phase11_e2e.py tests/test_backtest_agent_phase18_e2e.py tests/test_ui_mvp.py`
- `python3 scripts/check_docs_tree.py`
- `python3 scripts/check_subagent_packet.py --phase-id phase_38`

## 7) 预期产物（Artifacts）
- `jobs/<job_id>/outputs/agents/backtest/agent_run.json`
- `jobs/<job_id>/outputs/run_link.json`
- `dossiers/<run_id>/dossier_manifest.json`
- `dossiers/<run_id>/gate_results.json`

## 8) 完成记录（Execution Log）
- Start Date: 2026-02-11
- End Date: 2026-02-11
- Notes:
  - Published by orchestrator before execution.
  - Acceptance:
    - `docker compose run --rm api pytest -q tests/test_agents_orchestrator_phase11_e2e.py tests/test_backtest_agent_phase18_e2e.py tests/test_ui_mvp.py` -> pass
    - `python3 scripts/check_docs_tree.py` -> pass
    - `python3 scripts/check_subagent_packet.py --phase-id phase_38` -> pass
  - Packet hardened reconciliation uses `external_noise_paths` for known external workspace drift while keeping `allowed_paths` strictly limited to G18 implementation files.
