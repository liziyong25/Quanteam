# Phase-12: StrategySpecAgent v1 + CalcTrace Preview Checkpoint

## 1) 目标（Goal）
- 新增 StrategySpecAgent（harness 化）：把已批准的 blueprint draft 补全为 strategy DSL + var dict + trace plan，并产出 `blueprint_final.json`。
- 新增 CalcTrace Preview 阶段（deterministic）：在 runspec 审阅批准后，对小段数据做 trace preview，产出可审阅的 `calc_trace_preview.csv` + `trace_meta.json`。
- Orchestrator 增加新的审阅点：
  - `WAITING_APPROVAL(step=strategy_spec)`
  - `WAITING_APPROVAL(step=trace_preview)`

## 2) 范围（Scope）
### In Scope
- agents: `strategy_spec_agent_v1`
- diagnostics: `calc_trace_preview` executor
- orchestrator/jobstore/api/ui: workflow plumbing + review checkpoints
- tests: 离线 e2e 覆盖全链路
- docs: agents + trace preview 文档

### Out of Scope
- 不实现可执行回测脚本生成
- 不修改 policies 内容
- 不在 agent 层绕过 DataCatalog as_of 过滤

## 3) 验收（DoD）
- `docker compose build api worker`
- `EAM_UID=$(id -u) EAM_GID=$(id -g) docker compose run --rm api pytest -q`
- 串联（离线）：idea -> intent -> approve blueprint -> spec -> approve spec -> compile -> approve runspec -> trace preview -> approve -> run -> gates -> registry -> report -> DONE

## 4) 完成记录（Execution Log）
- Start Date: 2026-02-10 (Asia/Taipei)
- End Date: 2026-02-10 (Asia/Taipei)
- PR/Commit: unknown
- Notes:
  - Added StrategySpecAgent (mock deterministic) with contract-validated outputs.
  - Added CalcTrace preview artifacts from DataCatalog (as_of filtered).
  - Inserted new review checkpoints into orchestrator workflow.

