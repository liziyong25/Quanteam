# Phase-36: Spec-QA Agent Step and Checkpoint (G16)

## 1) 目标（Goal）
- 完成 G16：在 strategy_spec 审批后增加 `spec_qa` 机器校验步骤，并进入 `WAITING_APPROVAL(step=spec_qa)`。

## 2) 背景（Background）
- 当前 idea 工作流在 `strategy_spec` 审批后直接编译 runspec。
- SSOT G16 要求增加可审计的 Spec-QA 报告（JSON + Markdown）并作为独立审批检查点。

## 3) 范围（Scope）
### In Scope
- orchestrator 增加 Spec-QA 执行与 checkpoint 阻塞逻辑。
- 新增 `spec_qa_agent_v1`（通过 harness 执行）与 promptpack。
- approve 接口支持 `step=spec_qa`。
- UI job 详情页显示 spec_qa 报告证据。
- 新增/更新相关 e2e 测试。

### Out of Scope
- 修改 contracts/** 或 policies/**。
- 变更 holdout 可见性规则。

## 4) 任务卡（Task Card）
### Single Deliverable
- `G16` from `planned` to `implemented`.

### Allowed Paths
- `src/quant_eam/orchestrator/workflow.py`
- `src/quant_eam/agents/harness.py`
- `src/quant_eam/agents/spec_qa_agent.py`
- `prompts/agents/spec_qa_agent_v1/**`
- `src/quant_eam/api/jobs_api.py`
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/job.html`
- `tests/test_agents_orchestrator_phase11_e2e.py`
- `tests/test_spec_qa_phase16_e2e.py`
- `docs/08_phases/phase_36_spec_qa_agent_checkpoint_g16.md`
- `docs/12_workflows/agents_ui_ssot_v1.yaml`
- `artifacts/subagent_control/phase_36/**`

### Stop Conditions
- 触发 `autopilot_stop_conditions_v1` 任一项即暂停并上报用户；
- G16 的 route/API 变更仅在 `g16_spec_qa_step_scope` 例外范围内放行。

## 5) Subagent Control Packet
- `phase_id`: `phase_36`
- `packet_root`: `artifacts/subagent_control/phase_36/`
- evidence_policy: `hardened`

## 6) 验收标准（Acceptance Criteria / DoD）
- `docker compose run --rm api pytest -q tests/test_agents_orchestrator_phase11_e2e.py tests/test_spec_qa_phase16_e2e.py tests/test_ui_mvp.py`
- `python3 scripts/check_docs_tree.py`
- `python3 scripts/check_subagent_packet.py --phase-id phase_36`

## 7) 预期产物（Artifacts）
- `jobs/<job_id>/outputs/agents/spec_qa/spec_qa_report.json`
- `jobs/<job_id>/outputs/agents/spec_qa/spec_qa_report.md`
- `events.jsonl` 中出现 `WAITING_APPROVAL(step=spec_qa)` 并可审批继续。

## 8) 完成记录（Execution Log）
- Start Date: 2026-02-11
- End Date: 2026-02-11
- Notes:
  - Published by orchestrator before execution.
  - Acceptance:
    - `docker compose run --rm api pytest -q tests/test_agents_orchestrator_phase11_e2e.py tests/test_spec_qa_phase16_e2e.py tests/test_ui_mvp.py` -> pass
    - `python3 scripts/check_docs_tree.py` -> pass
    - `python3 scripts/check_subagent_packet.py --phase-id phase_36` -> pass
  - Added G16 stop-condition exception scope only for `spec_qa` checkpoint route/API behavior.
