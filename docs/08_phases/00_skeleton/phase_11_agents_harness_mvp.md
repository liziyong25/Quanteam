# Phase-11: Agents Harness MVP (Intent + Report) + Orchestrator Integration

## 1) 目标（Goal）
- 新增可执行 harness 的 agents 平面（deterministic、可审计）。
- IntentAgent：IdeaSpec -> Blueprint(v1) draft（声明式）。
- ReportAgent：Dossier + GateResults -> report artifacts（必须引用 artifacts）。
- 接入 Phase-10 工作流：支持提交 IdeaSpec，并在 blueprint/runspec 两处 checkpoint 等待批准。

## 2) 范围（Scope）
### In Scope
- contracts：IdeaSpec v1 / AgentRun v1
- agents harness：`run_agent(...)` + 两个 mock agent
- orchestrator：idea job 两段审批（blueprint/runspec）
- api/ui：提交 idea、按 step approve、jobs 页面展示 draft/runspec/report
- 离线 e2e tests

### Out of Scope
- 不实现 external provider（预留接口但 tests 不用）
- 不引入 LLM/Agents 自动裁决

## 3) 验收（DoD）
- `docker compose build api worker`
- `EAM_UID=$(id -u) EAM_GID=$(id -g) docker compose run --rm api pytest -q`
- API/worker 串联：
  - `POST /jobs/idea`
  - worker -> WAITING_APPROVAL(step=blueprint)
  - approve(step=blueprint)
  - worker -> WAITING_APPROVAL(step=runspec)
  - approve(step=runspec)
  - worker -> DONE（dossier+gate_results+trial_log+report）

## 4) 完成记录（Execution Log）
- Start Date: 2026-02-10 (Asia/Taipei)
- End Date: 2026-02-10 (Asia/Taipei)
- PR/Commit: unknown
- Notes:
  - Added IdeaSpec/AgentRun contracts + agents harness (mock).
  - Orchestrator supports idea jobs with two review checkpoints.
  - ReportAgent writes deterministic report artifacts referencing dossier/gate_results.

