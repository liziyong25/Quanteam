# Phase-26: Real LLM Provider v1 + Job-Level LLM Budget + Evidence

## 1) 目标（Goal）
- 增加一个可用的 real LLM provider（HTTP 调用），同时保持 tests/CI 完全离线（依赖 cassette replay）。
- 增加 job 级 LLM usage 证据与预算停止条件（calls/chars/wall time）。
- UI job 页展示 usage/预算消耗与 stop 原因。

## 2) 背景（Background）
- 接入真实 LLM 会引入非确定性与成本风险；必须通过 cassette replay + 预算治理确保可审计与可离线验收。
- usage 证据必须 append-only，避免被覆盖或篡改。

## 3) 范围（Scope）
### In Scope
- Real provider（HTTP）实现与配置
- `llm_budget_policy_v1` 资产与 validator
- `llm_usage_events.jsonl` + `llm_usage_report.json`（job 级证据）
- Harness + Orchestrator 双重 enforce
- UI job 页展示 usage/budget/stop reason

### Out of Scope
- tests 中的网络 IO（禁止）
- 修改任何既有 `*_v1.yaml` 内容（只新增文件）

## 4) 实施方案（Implementation Plan）
- provider：`EAM_LLM_PROVIDER=real` 时可走 HTTP；`EAM_LLM_MODE=replay` 强制仅用 cassette，不触发网络。
- budget policy：`policies/llm_budget_policy_v1.yaml` 提供阈值；job_spec/idea_spec 可通过 `llm_budget_policy_path` 指向自定义文件。
- evidence：
  - 每次 agent run 结束记录 usage event（append-only）
  - 聚合输出 usage report（可从 events 重建）
- enforce：
  - harness 预检查预算，超限则输出 budget stop evidence
  - orchestrator 发现 budget stop => `STOPPED_BUDGET` 并终止推进

## 5) 编码内容（Code Deliverables）
- `src/quant_eam/llm/providers/real_http.py`
- `policies/llm_budget_policy_v1.yaml`
- `src/quant_eam/jobstore/llm_usage.py`
- `contracts/llm_usage_report_schema_v1.json`
- `docs/13_agents/llm_budget_and_usage_v1.md`

## 6) 文档编写（Docs Deliverables）
- `docs/04_policies/llm_budget_policy_v1.md`
- `docs/13_agents/llm_budget_and_usage_v1.md`
- 本 phase log（本文件）

## 7) 验收标准（Acceptance Criteria / DoD）
- `pytest -q` 全绿（容器内）
- `python3 scripts/check_docs_tree.py` 通过
- 离线 budget stop 可复现：
  - 小预算触发 STOPPED_BUDGET
  - usage events/report 存在且可校验

## 8) 完成记录（Execution Log）
- Start Date: 2026-02-11 (Asia/Taipei)
- End Date: 2026-02-11 (Asia/Taipei)
- PR/Commit: unknown (git not available)
- Notes:
  - Added real provider + job-level budget evidence/enforcement.

## 9) 遗留问题（Open Issues）
- [ ] 将来可把 wall time 预算与系统调度（worker daemon）更严格对齐（当前以 best-effort 计时）。

## 10) Codex Prompt Footer

Append `docs/_snippets/codex_phase_footer.md` to the phase task card prompt for consistency.

