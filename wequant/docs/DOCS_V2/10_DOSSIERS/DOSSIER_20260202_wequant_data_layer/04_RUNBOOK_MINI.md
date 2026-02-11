---
title: WEQUANT data_layer — Runbook Mini
kind: dossier
component: data_layer
topics: [runbook, troubleshooting]
status: draft
created: 2026-02-02
updated: 2026-02-02
source_paths: []
related_modules: []
related_tables: []
keywords: [mongodb, timeout, index]
---

# 04_RUNBOOK_MINI（WEQUANT data_layer）

## Mongo 连接失败
- 检查 `WEQUANT_MONGO_URI`
- 检查 Mongo 服务端口与鉴权
- 用 `python -c "from wequant.mongo import get_db; print(get_db().list_collection_names())"` 快速定位

## 写入报 DuplicateKeyError
- 说明 unique index 生效且出现重复 key
- 检查写入数据中 `(code, date)` 是否重复（同批次内部重复）
- 在写入前去重：`df.drop_duplicates(["code","date"])`

## 取数为空
- 确认集合名是否与实际一致（ETF 是否在 stock_day 或 etf_day）
- 确认 date 字段类型是否为 BSON Date（而非字符串）
