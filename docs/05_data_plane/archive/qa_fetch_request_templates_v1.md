# QA Fetch Request Templates v1

> Deprecated for new Agent integrations.  
> Use `docs/05_data_plane/agents_plane_data_contract_v1.md` as the primary contract for Agents Plane dataset/query semantics.

## 1) 放在哪里

当前工作流会按以下优先级读取 `fetch_request`：

1. `job_spec.fetch_request`（推荐）
2. `job_spec.extensions.fetch_request`（兼容）
3. `runspec.extensions.fetch_request`（回退）

实现位置：

- `src/quant_eam/orchestrator/workflow.py:471`
- `src/quant_eam/orchestrator/workflow.py:525`

执行入口：

- `src/quant_eam/agents/demo_agent.py:65`
- `src/quant_eam/agents/backtest_agent.py:65`
- `src/quant_eam/qa_fetch/runtime.py:63`

证据产物目录：

- `jobs/<job_id>/outputs/fetch/fetch_request.json`
- `jobs/<job_id>/outputs/fetch/fetch_result_meta.json`
- `jobs/<job_id>/outputs/fetch/fetch_preview.csv`
- `jobs/<job_id>/outputs/fetch/fetch_error.json`（失败时）

## 2) 模板A：按 intent（推荐给 LLM）

```json
{
  "fetch_request": {
    "mode": "smoke",
    "policy": {
      "mode": "smoke",
      "timeout_sec": 30,
      "on_no_data": "pass_empty"
    },
    "intent": {
      "asset": "bond",
      "freq": "day",
      "venue": null,
      "adjust": "raw",
      "symbols": "240011.IB",
      "start": "2026-01-01",
      "end": "2026-02-11",
      "extra_kwargs": {}
    },
    "window_profile_path": "docs/05_data_plane/qa_fetch_smoke_window_profile_v1.json",
    "exception_decisions_path": "docs/05_data_plane/qa_fetch_exception_decisions_v1.md"
  }
}
```

适用场景：

- LLM 给出“资产+频率+来源+复权”语义请求。
- 由 resolver 自动选函数。

## 3) 模板B：按 function（精确指定函数）

```json
{
  "fetch_request": {
    "mode": "backtest",
    "policy": {
      "mode": "backtest",
      "timeout_sec": null,
      "on_no_data": "pass_empty"
    },
    "function": "fetch_stock_day",
    "source_hint": "wequant",
    "public_function": "fetch_stock_day",
    "kwargs": {
      "code": ["000001"],
      "start": "2024-01-01",
      "end": "2024-12-31",
      "format": "pd"
    },
    "window_profile_path": "docs/05_data_plane/qa_fetch_smoke_window_profile_v1.json",
    "exception_decisions_path": "docs/05_data_plane/qa_fetch_exception_decisions_v1.md"
  }
}
```

适用场景：

- 你已经明确要调用哪个 `fetch_*`。
- 不希望 resolver 参与决策。

## 4) 参数优先级（Agent/LLM 需要知道）

- `LLM输入参数` > `window profile smoke_kwargs` > `函数默认参数`
- `smoke` 默认 30s；`research/backtest` 默认不限时（除非你显式给 `timeout_sec`）

实现位置：

- `src/quant_eam/qa_fetch/runtime.py:149`
- `src/quant_eam/qa_fetch/runtime.py:156`

## 5) 真实 job_spec 示例（idea_spec_v1）

> 只展示关键字段；其余保留你现有内容。

```json
{
  "schema_version": "idea_spec_v1",
  "title": "Bond demo with qa_fetch",
  "hypothesis_text": "Use qa_fetch data for preview/backtest.",
  "symbols": ["240011.IB"],
  "frequency": "1d",
  "start": "2026-01-01",
  "end": "2026-02-11",
  "evaluation_intent": "qa_fetch_trial",
  "snapshot_id": "demo_snap_qa_fetch_001",
  "policy_bundle_path": "policies/policy_bundle_v1.yaml",
  "fetch_request": {
    "mode": "smoke",
    "policy": {"mode": "smoke", "timeout_sec": 30, "on_no_data": "pass_empty"},
    "intent": {
      "asset": "bond",
      "freq": "day",
      "venue": null,
      "adjust": "raw",
      "symbols": "240011.IB",
      "start": "2026-01-01",
      "end": "2026-02-11"
    },
    "window_profile_path": "docs/05_data_plane/qa_fetch_smoke_window_profile_v1.json",
    "exception_decisions_path": "docs/05_data_plane/qa_fetch_exception_decisions_v1.md"
  }
}
```

## 6) 7 个 pending 的建议（先稳定系统）

建议本轮全部标 `drop`，避免 Agent 跑到不可用函数：

- `fetch_bond_min`（缺表）
- `fetch_cfets_repo_item`（缺表）
- `fetch_clean_quote`（缺表）
- `fetch_realtime_min`（缺表）
- `fetch_future_tick`（未实现）
- `fetch_quotation`（上游结构不匹配）
- `fetch_quotations`（上游结构不匹配）

如果后续源表/上游修复，再把对应函数改为 `allow`。
