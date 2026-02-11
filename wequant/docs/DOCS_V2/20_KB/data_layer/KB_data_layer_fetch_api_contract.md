---
title: WEQUANT data_layer - Fetch API Contract (v0)
kind: kb
component: data_layer
topics: [fetch, api_contract]
status: draft
created: 2026-02-02
updated: 2026-02-03
source_paths:
  - wequant/wefetch
related_modules:
  - wequant/wefetch/stock.py
  - wequant/wefetch/future.py
  - wequant/wefetch/etf.py
  - wequant/wefetch/adj.py
  - wequant/wefetch/lists.py
related_tables: []
keywords: [WEFetch, stock_day, future_day, etf, adj]
---

# Fetch API Contract (v0)
目标：提供与 QUANTAXIS 接近的 Mongo 读接口（stock/future/ETF + list + adj）。

## Public functions (v0)
- `wequant.wefetch.fetch_stock_day(codes, start, end, *, fields=None, adjust="none", format="pd")`
- `wequant.wefetch.fetch_etf_day(codes, start, end, *, fields=None, adjust="none", format="pd")`
- `wequant.wefetch.fetch_future_day(codes, start, end, *, fields=None, format="pd")`
- `wequant.wefetch.fetch_stock_adj(codes, start, end, *, fields=None, format="pd")`
- `wequant.wefetch.fetch_stock_list()`
- `wequant.wefetch.fetch_etf_list()`
- `wequant.wefetch.fetch_future_list()`

## Format semantics
- `format="pd"`: DataFrame
- `format="json"/"dict"`: list[dict]（`date/datetime` 转为字符串）
- `format="numpy"` / `format="list"`: numpy 或 list

## Date semantics
- `start/end` 为闭区间（inclusive）
- 日线查询优先 `date_stamp`；无则回退到 `date`

## Optional fields
- `fields`: 可选列白名单（投影后再输出；若列缺失将被忽略）

## Output columns
- Stock day: `code, open, high, low, close, volume, amount, date`（index=`date`）
- Future day: `code, open, high, low, close, position, price, trade, date`（index=`date`）
- Stock adj: `code, date, adj`（index=`date`）
- List: `code` 为 index（保留原字段）

## ETF 日线集合选择
- 默认 `stock_day`
- 若设置 `WEQUANT_ETF_DAY_COLLECTION` 则强制使用
- 若 `etf_day` 存在且 `stock_day` 未包含 ETF 代码，则切换 `etf_day`

## Adjust semantics (staged)
- v0：仅 raw（`adjust="none"`）
- v1：支持 qfq/hfq（基于 `stock_adj`）
