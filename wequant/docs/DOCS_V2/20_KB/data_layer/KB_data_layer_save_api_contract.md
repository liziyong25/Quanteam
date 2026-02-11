---
title: WEQUANT data_layer - Save API Contract (v0)
kind: kb
component: data_layer
topics: [save, api_contract, upsert]
status: draft
created: 2026-02-03
updated: 2026-02-03
source_paths:
  - wequant/wesu
related_modules:
  - wequant/wesu/stock.py
  - wequant/wesu/future.py
  - wequant/wesu/etf.py
  - wequant/wesu/adj.py
  - wequant/wesu/lists.py
related_tables:
  - stock_day
  - future_day
  - stock_adj
  - stock_list
  - future_list
  - etf_list
keywords: [WESU, upsert, idempotent]
---

# Save API Contract (v0)
目标：提供与 QUANTAXIS 行为对齐的 Mongo 写接口（幂等 upsert）。

## Public functions (v0)
- `wequant.wesu.save_stock_day(df, *, upsert=True)`
- `wequant.wesu.save_future_day(df, *, upsert=True)`
- `wequant.wesu.save_etf_day(df, *, upsert=True)`
- `wequant.wesu.save_stock_adj(df, *, upsert=True)`
- `wequant.wesu.save_stock_list(df, *, upsert=True)`
- `wequant.wesu.save_future_list(df, *, upsert=True)`
- `wequant.wesu.save_etf_list(df, *, upsert=True)`

## Input expectations
- `df` 为 pandas DataFrame
- 需要 `code` + `date` 字段（日线）
- `date` 会被规范化为 `YYYY-MM-DD` 字符串
- `date_stamp` 自动补齐（日线）
- stock/ETF 若缺 `vol`，会从 `volume` 补齐
- future 若缺 `trade`，会从 `volume/vol` 补齐

## Idempotency
- 使用 `UpdateOne(..., upsert=True)` 实现幂等写入
- unique(`code`,`date`) 约束保证不重复

## ETF 日线集合选择
- 默认写入 `stock_day`
- 若设置 `WEQUANT_ETF_DAY_COLLECTION` 则强制写入
- 若 `etf_day` 存在且 `stock_day` 未包含 ETF 代码，则写入 `etf_day`
