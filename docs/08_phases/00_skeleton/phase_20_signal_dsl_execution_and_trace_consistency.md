# Phase-20: Signal DSL Execution Expansion + Trace Consistency v1

## 1) 目标（Goal）
- 扩展 `vectorbt_signal_v1` 对 `signal_dsl_v1` 的可执行覆盖（MA crossover + RSI mean reversion）。
- 引入单一真理层 `signal_compiler`，让 calc trace preview 与 backtest 使用同一套信号编译逻辑。
- 强制 no-lookahead：`lag_bars >= 1`，并提供离线回归测试。

## 2) 背景（Background）
- Phase-04 的 backtest 仅支持 `buy_and_hold_mvp`，而 Phase-07/14/19 之后 Agents 已能输出 `signal_dsl_v1`。
- 如果 trace preview 和 backtest 各自计算信号，会出现“预览与执行不一致”的审阅风险。

## 3) 范围（Scope）
### In Scope
- `src/quant_eam/backtest/signal_compiler.py`：可执行子集的 DSL 编译（SMA/RSI/cross + lag）。
- `src/quant_eam/backtest/vectorbt_adapter_mvp.py`：支持传入 `signal_dsl_v1` 并执行。
- `src/quant_eam/diagnostics/calc_trace_preview.py`：改为复用 signal compiler，输出 raw/lagged + intermediates。
- StrategySpecAgent：最小扩展，支持 deterministic 生成 MA/RSI DSL fixtures（通过 IdeaSpec.extensions.strategy_template）。
- tests + docs 补齐。

### Out of Scope
- 不修改 `policies/**` v1。
- 不引入网络 IO；tests 离线 deterministic。

## 4) 实施方案（Implementation Plan）
- 统一信号语义：cross 的定义、rolling 指标的 per-symbol 计算与稳定排序。
- 统一 lag：`entry_lagged/exit_lagged` 在 compiler 层 shift，且 lag>=1。
- Trace preview 输出包含可审阅列，`trace_meta.json` 写入 `dsl_fingerprint` 与 `signals_fingerprint` 以便一致性断言。

## 5) 编码内容（Code Deliverables）
- `src/quant_eam/backtest/signal_compiler.py`
- `src/quant_eam/backtest/vectorbt_adapter_mvp.py`（新增 `run_signal_dsl_v1` + `run_adapter(..., signal_dsl=...)`）
- `src/quant_eam/diagnostics/calc_trace_preview.py`（复用 compiler；扩展 CSV/meta）
- `src/quant_eam/agents/strategy_spec_agent.py`（模板输出 + var_dict/trace_plan 补齐 exit 与指标列）
- `tests/test_signal_dsl_execution_phase20.py`
- `tests/fixtures/agents/strategy_spec_agent_v1/{ma_crossover_case,rsi_mean_reversion_case}/...`

## 6) 文档编写（Docs Deliverables）
- 新增：`docs/06_backtest_plane/signal_dsl_execution_v1.md`
- 更新：`docs/14_trace_preview/trace_preview_v1.md`
- 本 phase log：`docs/08_phases/00_skeleton/phase_20_signal_dsl_execution_and_trace_consistency.md`

## 7) 验收标准（Acceptance Criteria / DoD）
- `EAM_UID=$(id -u) EAM_GID=$(id -g) docker compose run --rm api pytest -q`
- `python3 scripts/check_docs_tree.py`

## 8) 完成记录（Execution Log）
- Start Date: 2026-02-10
- End Date: 2026-02-10
- Notes:
  - Signal compiler 提供可执行子集（SMA/RSI/cross）；lag>=1 强制 no-lookahead。
  - Trace preview 与 backtest 使用同一 compiler，并用 `signals_fingerprint` 做一致性断言。

## 10) Codex Prompt Footer

Append `docs/_snippets/codex_phase_footer.md` to the phase task card prompt for consistency.

