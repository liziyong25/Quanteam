# QA Fetch 集成说明（给 GPT Pro 评审）

## 1. 文档目的
本文件用于让 GPT Pro 快速评审并出实施方案，回答两个核心问题：

1. `fetch_*` 迁移到 quanteam 的进度到哪里了。
2. 现在应该如何把 `fetch_*` 能力嵌入到 UI + LLM Agent 主链路。

约束：本说明以当前仓库事实为准，不讨论历史目录 `WBData/`、`wequant/` 的旧实现细节。

---

## 2. 当前状态快照（截至当前仓库）

### 2.1 函数基线
- 主基线函数数：`71`
- 主文件：`docs/05_data_plane/qa_fetch_function_registry_v1.json`
- 对外语义：`source=fetch`
- 引擎拆分：`engine=mongo|mysql`
- 当前引擎分布：`mongo=48`, `mysql=23`

### 2.2 机器注册表
- 机器路由表：`docs/05_data_plane/qa_fetch_registry_v1.json`
- `source` 已统一为 `fetch`
- `provider_id` 已统一为 `fetch`
- 保留内部追踪字段：`source_internal`, `provider_internal`

### 2.3 可用性证据（Notebook 参数标准）
- 证据文件：`docs/05_data_plane/qa_fetch_probe_v3/probe_summary_v3_notebook_params.json`
- 全量覆盖：`71`
- 状态：
  - `pass_has_data=52`
  - `pass_empty=19`
- 结论：**全部可调用，无 runtime 阻塞项**（按当前 smoke 口径）。

### 2.4 运行入口（已接入）
- 统一运行层：`src/quant_eam/qa_fetch/runtime.py`
  - `execute_fetch_by_intent(...)`
  - `execute_fetch_by_name(...)`
- Agent 已调用 runtime：
  - `src/quant_eam/agents/demo_agent.py`
  - `src/quant_eam/agents/backtest_agent.py`

### 2.5 当前判断
**可以嵌入 quanteam 主流程**。
不是“准备中”，而是已经具备可集成的 fetch 运行能力与证据落盘能力。

---

## 3. 与两份总纲文档的关系

## 3.1 对应 `Quant‑EAM Whole View Framework.md`
重点对齐章节：
- `2. 总体架构：五个平面`
- `6.1 Data Plane`
- `6.4 Agents Plane`

对齐解释：
1. `qa_fetch` 当前是 Data Plane 的“外部抓取执行层”（fetch runtime），为 DataLake/DataCatalog 提供数据入口能力。
2. Agent 不应直接硬编码底层 provider，而应调用 runtime，并输出证据到 dossier/job outputs。
3. 对用户而言，UI 侧语义应是“我要什么数据”（intent），而不是“调用哪个库”。

## 3.2 对应 `Quant‑EAM Implementation Phases Playbook.md`
重点对齐阶段：
- `Phase-3 Data Plane MVP`：数据接入与 catalog 主线
- `Phase-6 UI MVP`：UI 可审阅证据
- `Phase-8 Agents v1`：agent harness 化运行

当前落点：
1. Phase-3：fetch 入口已形成统一 runtime 与 registry。
2. Phase-8：agent 已可通过 runtime 取数并落证据。
3. 下一步是把 UI 请求语义稳定映射到 `fetch_request` / `intent`（Phase-6 + Phase-8 联动）。

---

## 4. 推荐的嵌入方式（主链路）

## 4.1 总体调用链
`UI -> Orchestrator -> Agent(fetch_request) -> qa_fetch.runtime -> fetch evidence -> (可选) DataLake ingest -> DataCatalog query_dataset`

要点：
1. **LLM 先做语义决策**（asset/freq/venue/adjust/symbols/time range）。
2. **runtime 做函数解析与执行**，不让 agent 直接 import provider。
3. **证据必须落盘**，用于可审计回放。

## 4.2 fetch_request 建议标准
优先使用 `intent` 方式，`function` 仅在你要强控函数时使用。

示例（intent 方式）：

```json
{
  "fetch_request": {
    "mode": "backtest",
    "intent": {
      "asset": "stock",
      "freq": "day",
      "venue": null,
      "adjust": "raw",
      "symbols": ["600519"],
      "start": "2010-01-01",
      "end": "2025-12-31"
    },
    "policy": {
      "mode": "backtest",
      "on_no_data": "error"
    }
  }
}
```

证据输出（必须）：
- `jobs/<job_id>/outputs/fetch/fetch_request.json`
- `jobs/<job_id>/outputs/fetch/fetch_result_meta.json`
- `jobs/<job_id>/outputs/fetch/fetch_preview.csv`
- `jobs/<job_id>/outputs/fetch/fetch_error.json`（失败时）

---

## 5. 你提出的 MA250 例子：应如何被 Agent 自动完成
用户意图示例：
> 我要测试 A 股 MA250 年线策略作用。

### 5.1 Agent 预期步骤
1. 识别资产语义：`A股 -> asset=stock, freq=day`。
2. 若用户未给 code：先调用 `fetch_stock_list` 获取候选股票集合。
3. 选择测试样本（可按流动性、行业、市值或随机分层）。
4. 对每个样本调用 `fetch_stock_day(code,start,end)`。
5. 在 agent 内计算 `MA250` 并形成回测输入或 demo trace。

### 5.2 最小两段取数流程（建议）
1. 列表取数：
- `fetch_stock_list()`
2. 行情取数：
- `fetch_stock_day(code,start,end)`

这和你的目标一致：
- LLM 先理解“测试目标”
- 自动决定“先拿列表再拿K线”
- 无需人工先写死 code

---

## 6. 给 GPT Pro 的实现建议（可直接评审）

## 6.1 Prompt/Planner 层
新增一段固定规划规则：
1. 如果用户未提供 symbol/code，先尝试对应 `*_list`。
2. 如果任务是技术指标（MA/RSI/MACD），默认需要 `day` 级 OHLCV。
3. 默认 `adjust=raw`，如用户说“前复权/后复权”再切换。

## 6.2 Resolver 层
使用 `execute_fetch_by_intent` 为主：
- 减少模型硬编码函数名
- 提升跨函数扩展能力

## 6.3 失败回退策略
1. `pass_empty`：切换 symbol 或缩短窗口重试。
2. `error_runtime`：输出 `fetch_error.json` 并提示“参数/数据源异常”。
3. 保证每次都产证据文件，避免黑盒失败。

---

## 7. 你现在最应该做的三件事

1. 在 Orchestrator 的 job_spec 固化 `fetch_request.intent` 契约。
2. 在 UI 层加入“是否自动补全样本（先 list 后 day）”开关。
3. 给 Agent 增加 3 条策略意图模板（如 MA250、突破、均值回归），验证自动选函数是否稳定。

---

## 8. 当前阶段结论（给评审的一句话）
`fetch_*` 已完成可运行迁移与外部语义统一（`source=fetch` + `engine`），并已接入 agent runtime。
下一阶段不是“能不能接入”，而是“把 UI 意图到 fetch_request 的自动规划做稳定”。

---

## 9. 关键文件索引（评审必看）
- 总蓝图：`Quant‑EAM Whole View Framework.md`
- 实施分期：`Quant‑EAM Implementation Phases Playbook.md`
- fetch runtime：`src/quant_eam/qa_fetch/runtime.py`
- fetch resolver：`src/quant_eam/qa_fetch/resolver.py`
- 函数注册表：`docs/05_data_plane/qa_fetch_function_registry_v1.json`
- 路由注册表：`docs/05_data_plane/qa_fetch_registry_v1.json`
- smoke 证据：`docs/05_data_plane/qa_fetch_probe_v3/probe_summary_v3_notebook_params.json`
- agent 调用示例：`src/quant_eam/agents/demo_agent.py`, `src/quant_eam/agents/backtest_agent.py`
