---
title: WEQUANT data_layer — Function-level Dataflow (MongoDB → WESU/WEFetch → Research)
kind: dossier_dataflow
component: data_layer
topics: [dataflow, functions]
status: draft
created: 2026-02-02
updated: 2026-02-02
---

# 06_DATAFLOW_FUNCTION_LEVEL（wequant_data_layer）

## Part 1：Mermaid（模块级）

```mermaid
flowchart LR
  subgraph DB[(MongoDB)]
    T1[stock_day/future_day/stock_adj]
    T2[stock_list/future_list/etf_list]
  end

  subgraph lib[WEQUANT]
    W1[wesu::* save_*_day / save_stock_adj]
    W2[wefetch::* fetch_*_day / fetch_stock_adj]
  end

  subgraph research[Research / Backtest]
    R1[vectorbt notebooks / scripts]
  end

  T1 --> W2 --> R1
  T2 --> W2 --> R1
  R1 --> W1 --> T1
```

## Part 2：函数级流水账（核心）

### 1) `wequant/wesu/stock.py::save_stock_day(df)`
- 输入：包含 code/date/OHLCV 的 DataFrame
- 输出：bulk upsert 写入 stock_day（幂等）
- 角色：数据落库/更新
- 下一跳：MongoDB `stock_day`

### 2) `wequant/wefetch/stock.py::fetch_stock_day(codes, start, end, adjust)`
- 输入：codes + 日期区间
- 输出：raw 日线 DataFrame（date normalize）
- 角色：研究/回测取数入口
- 下一跳：vectorbt / 策略模块

### 3) `wequant/wefetch/adj.py::fetch_stock_adj(...)`
- 输入：codes + 日期区间
- 输出：复权因子（用于 qfq/hfq）
- 角色：口径对齐（指标/价格）
- 下一跳：策略指标计算 / 价格复权

## Part 3：最小对照表

| Layer | Artifact | Name | Consumed by |
|---|---|---|---|
| DB | collection | stock_day | wefetch.fetch_stock_day |
| DB | collection | future_day | wefetch.fetch_future_day |
| DB | collection | stock_adj | wefetch.fetch_stock_adj |
| Library | function | wesu.save_stock_day | MongoDB |
| Library | function | wefetch.fetch_stock_day | vectorbt |
| Consumer | notebook/script | (your research) | end-user |

## Evidence（Run-backed）
- 见 `05_ACCEPTANCE_EVIDENCE.md`（必须实际回填命令输出）
