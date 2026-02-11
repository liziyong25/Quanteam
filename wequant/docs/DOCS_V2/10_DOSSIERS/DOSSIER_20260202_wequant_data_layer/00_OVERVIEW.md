---
title: WEQUANT data_layer — Overview (SSOT)
kind: dossier
component: data_layer
topics: [data_layer, wefetch, wesu, mongodb, quantaxis_migration]
status: draft
created: 2026-02-02
updated: 2026-02-02
source_paths:
  - wequant/wefetch
  - wequant/wesu
related_modules:
  - wequant/wefetch/__init__.py
  - wequant/wesu/__init__.py
  - wequant/config.py
related_tables:
  - stock_day
  - future_day
  - stock_adj
  - stock_list
  - future_list
  - etf_list
keywords: [WEFetch, WESU, SSOT, day_frequency]
---

# WEQUANT data_layer（SSOT）

## Final
- 目标：从 QUANTAXIS 的 QAFetch/QASU 抽离出**最小可用**的数据层，实现 WEFetch/WESU（仅 股票/期货/ETF）。
- 存储：复用现有 MongoDB collections（不重建、不迁移）。
- 运行形态：日频、研究为主；不引入实时微服务。
- 兼容策略：先对齐你现有 notebook 的用法（取数/存数语义），再逐步替换内部实现。

## Contracts
- Public API：见 `20_KB/data_layer/KB_data_layer_fetch_api_contract.md`
- Schema/Index：见 `20_KB/data_layer/KB_data_layer_schema_and_indexing.md`
- ENV：见本 Dossier `02_ENV_CONTRACT.md`

## Verification Order
1) `pip install -e .` 可用
2) Mongo 连接可用（能读 `stock_list`）
3) WEFetch 能取到 `stock_day` / `future_day` / `stock_adj`
4) WESU 能幂等写入（重复执行 row count 不漂移）
5) 与现有 QUANTAXIS fetch 结果对齐（抽样对比）

## Rollback
- WEFetch/WESU 只读/只写 Mongo，不改原始历史数据结构；回滚=停止使用 wequant 包，回到 QUANTAXIS 直连即可。

## Lessons
- Path Contract：绝对路径只允许出现在 `99_WORKSPACE.md`
- 写入必须幂等：unique index + bulk upsert
