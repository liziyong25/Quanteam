---
title: WEQUANT data_layer - Schema & Indexing (MongoDB)
kind: kb
component: data_layer
topics: [schema, indexing, mongodb]
status: draft
created: 2026-02-02
updated: 2026-02-03
source_paths:
  - wequant/wesu/stock.py
  - wequant/wesu/future.py
  - wequant/wesu/adj.py
related_modules:
  - wequant/wesu/stock.py
  - wequant/wesu/future.py
  - wequant/wesu/adj.py
related_tables:
  - stock_day
  - future_day
  - stock_adj
  - stock_list
  - future_list
  - etf_list
keywords: [unique_index, idempotent, upsert, date_stamp]
---

# Schema & Indexing (v0)
本项目复用现有 MongoDB collections（QUANTAXIS 生态）。

## Core collections
- `stock_day`
- `future_day`
- `stock_adj`
- `stock_list`
- `future_list`
- `etf_list`

## Key fields
- Day 数据建议包含：
  - `code`（string）
  - `date`（YYYY-MM-DD string）
  - `date_stamp`（float, unix seconds）
  - `vol`（stock/ETF）
  - `trade`（future）
- `stock_adj`: `code, date, adj`

## Minimal indexes (required)
- `stock_day`: unique(`code`, `date`)
- `future_day`: unique(`code`, `date`)
- `stock_adj`: unique(`code`, `date`)
- 建议附加非唯一索引：(`code`, `date_stamp`) 加速范围查询

## Idempotency rule
- 写入使用 bulk upsert（`UpdateOne(..., upsert=True)`）
- 同一批数据重复写入不产生重复行/漂移
