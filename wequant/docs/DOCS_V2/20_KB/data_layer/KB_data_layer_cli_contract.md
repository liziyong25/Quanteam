---
title: WEQUANT data_layer - CLI Contract (v0)
kind: kb
component: data_layer
topics: [cli, contract, tools]
status: draft
created: 2026-02-03
updated: 2026-02-03
source_paths:
  - wequant/cli.py
related_modules:
  - wequant/cli.py
related_tables: []
keywords: [wequant, doctor, init-indexes, smoke-fetch, smoke-save]
---

# CLI Contract (v0)

## Commands
- `wequant doctor`
  - 输出 `WEQUANT_MONGO_URI`, `WEQUANT_DB_NAME`
  - 执行 `mongo_ping`
  - 检查关键集合是否存在/是否有数据

- `wequant init-indexes`
  - 创建 `stock_day/future_day/stock_adj` 的 unique(`code`,`date`)
  - 创建辅助索引 (`code`,`date_stamp`)

- `wequant smoke-fetch --type {stock|future|etf} --code CODE[,CODE] --start YYYY-MM-DD --end YYYY-MM-DD`
  - 打印返回行数 + head(5)

- `wequant smoke-save --type {stock|future|etf|adj} [--csv FILE] [--code CODE --date YYYY-MM-DD ...]`
  - `--csv` 未提供时使用内置样例行
  - 输出 `written_ops`
