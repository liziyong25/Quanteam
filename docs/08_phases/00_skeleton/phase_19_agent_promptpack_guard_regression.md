# Phase-19: Agent PromptPack + Output Guard + Regression Suite v1

## 1) 目标（Goal）
- 让 Agents 在接入 LLM 后仍可稳定迭代：prompt 版本化、输出治理护栏、离线回归与 UI 证据增强。

## 2) 背景（Background）
- Phase-18 引入了 LLM cassette record/replay，但 prompt 演进与输出治理需要进一步固化，避免“误命中 replay”与治理边界漂移。
- 本 Phase 强化 Agents plane 的 determinism 与 evidence 链：PromptPack + output guard + regression cases。

## 3) 范围（Scope）
### In Scope
- PromptPack 目录规范与元信息（prompt_version / output_schema_version）。
- prompt_hash 组成包含 prompt_version/output_schema_version/输入 redaction hash（避免漂移误命中）。
- Output Guard（硬规则）与 evidence 化落盘。
- UI 展示 prompt_version / output_schema_version / guard_status（只读证据）。
- Regression Suite v1（fixtures + runner + tests），离线 deterministic。

### Out of Scope
- 引入真实网络 LLM provider（保持离线；真实 provider 仅 stub/未来 Phase）。
- 修改 policies v1 / contracts v1 的既有内容（只新增/补齐必要 docs/fixtures）。

## 4) 实施方案（Implementation Plan）
- PromptPack:
  - `prompts/agents/<agent_id>/prompt_vN.md` 版本化。
  - 文件头写 `prompt_version` 与 `output_schema_version`，harness 记录到 `llm_session.json`。
- Hashing:
  - `prompt_hash` 基于 canonical 的 request 对象，其中包含 prompt_version、output_schema_version、promptpack_sha256 与 redaction hash。
- Output Guard:
  - 对 agent 输出 bundle 做 deterministic walk，阻止：
    - inline policy params / policy overrides
    - executable script/code keys
    - holdout details
  - 输出 `output_guard_report.json`，UI 作为证据展示。
- Regression:
  - `tests/fixtures/agents/...` 固化样例输入与期望输出。
  - 提供离线 runner `python -m quant_eam.agents.regression`。

## 5) 编码内容（Code Deliverables）
- 目录范围：`src/quant_eam/agents/**`, `tests/**`, `prompts/**`, `contracts/**`, `docs/**`, `scripts/check_docs_tree.py`
- 新增/修改文件清单：
  - `src/quant_eam/agents/regression.py`（离线回归 runner）
  - `tests/fixtures/agents/...`（回归样例）
  - `tests/test_agents_regression_suite_phase19.py`（回归 runner 测试）
  - `docs/13_agents/promptpack_and_regression_v1.md`
  - `docs/08_phases/00_skeleton/phase_19_agent_promptpack_guard_regression.md`

## 6) 文档编写（Docs Deliverables）
- 新增：
  - `docs/13_agents/promptpack_and_regression_v1.md`
  - `docs/08_phases/00_skeleton/phase_19_agent_promptpack_guard_regression.md`
- 更新：
  - `scripts/check_docs_tree.py` required list

## 7) 验收标准（Acceptance Criteria / DoD）
### 必须可执行的验收命令
- `EAM_UID=$(id -u) EAM_GID=$(id -g) docker compose run --rm api pytest -q`
- `python3 scripts/check_docs_tree.py`
- `python -m quant_eam.agents.regression --agent intent_agent_v1 --cases tests/fixtures/agents/intent_agent_v1`

### 预期产物（Artifacts）
- Agent run evidence（每次 agent harness run）：
  - `llm_calls.jsonl`, `llm_session.json`, `redaction_summary.json`, `output_guard_report.json`
- UI Job 页面 “LLM Evidence” 区块展示 prompt_version / output_schema_version / guard_status。

## 8) 完成记录（Execution Log）
- Start Date: 2026-02-10
- End Date: 2026-02-10
- Notes:
  - Regression suite 默认离线 mock；prompt 演进通过 prompt_hash 变化避免 cassette 误命中。

## 9) 遗留问题（Open Issues）
- [ ] 如未来引入真实 provider：需要新增 ADR 定义 provider 接入与 redaction 边界、速率与成本治理。

## 10) Codex Prompt Footer

Append `docs/_snippets/codex_phase_footer.md` to the phase task card prompt for consistency.

