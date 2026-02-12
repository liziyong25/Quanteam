# Phase-37: Demo Agent Step Integration (G17)

## 1) 目标（Goal）
- 完成 G17：在 runspec 审批后加入 demo agent 步骤，生成 demo agent 运行证据，并产出 deterministic trace preview 后停在 `trace_preview` 审批点。

## 2) 背景（Background）
- 当前 trace preview 由 orchestrator 直接生成，尚无 `outputs/agents/demo/agent_run.json` 证据。
- G17 要求 demo 步骤被显式集成，并且不引入新的 route/schema 变更。

## 3) 范围（Scope）
### In Scope
- 新增 `demo_agent_v1`（harness 可执行）与 promptpack。
- orchestrator 在 trace preview 阶段前运行 demo agent 并记录输出索引。
- 新增/更新 e2e 测试覆盖 demo agent 证据链。

### Out of Scope
- 修改 API route/schema。
- 修改 contracts/** 或 policies/**。

## 4) 任务卡（Task Card）
### Single Deliverable
- `G17` from `planned` to `implemented`.

### Allowed Paths
- `src/quant_eam/orchestrator/workflow.py`
- `src/quant_eam/agents/harness.py`
- `src/quant_eam/agents/demo_agent.py`
- `prompts/agents/demo_agent_v1/**`
- `tests/test_agents_orchestrator_phase11_e2e.py`
- `tests/test_demo_agent_phase17_e2e.py`
- `docs/08_phases/00_skeleton/phase_37_demo_agent_step_integration_g17.md`
- `docs/12_workflows/skeleton_ssot_v1.yaml`
- `artifacts/subagent_control/phase_37/**`

### Stop Conditions
- 触发 `autopilot_stop_conditions_v1` 任一项即暂停并上报用户。

## 5) Subagent Control Packet
- `phase_id`: `phase_37`
- `packet_root`: `artifacts/subagent_control/phase_37/`
- evidence_policy: `hardened`

## 6) 验收标准（Acceptance Criteria / DoD）
- `docker compose run --rm api pytest -q tests/test_agents_orchestrator_phase11_e2e.py tests/test_demo_agent_phase17_e2e.py tests/test_ui_mvp.py`
- `python3 scripts/check_docs_tree.py`
- `python3 scripts/check_subagent_packet.py --phase-id phase_37`

## 7) 预期产物（Artifacts）
- `jobs/<job_id>/outputs/agents/demo/agent_run.json`
- `jobs/<job_id>/outputs/calc_trace_preview.csv`
- `jobs/<job_id>/outputs/trace_meta.json`
- `jobs/<job_id>/events.jsonl`（包含 trace_preview checkpoint）

## 8) 完成记录（Execution Log）
- Start Date: 2026-02-11
- End Date: 2026-02-11
- Notes:
  - Published by orchestrator before execution.
  - Acceptance:
    - `docker compose run --rm api pytest -q tests/test_agents_orchestrator_phase11_e2e.py tests/test_demo_agent_phase17_e2e.py tests/test_ui_mvp.py` -> pass
    - `python3 scripts/check_docs_tree.py` -> pass
    - `python3 scripts/check_subagent_packet.py --phase-id phase_37` -> pass
