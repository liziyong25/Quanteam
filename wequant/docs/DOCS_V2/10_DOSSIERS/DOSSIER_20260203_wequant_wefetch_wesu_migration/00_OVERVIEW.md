---
title: WEQUANT WEFetch/WESU Migration - Overview (SSOT)
kind: dossier
component: data_layer
topics: [data_layer, wefetch, wesu, mongodb, quantaxis_migration]
status: draft
created: 2026-02-03
updated: 2026-02-03
source_paths:
  - wequant/wefetch
  - wequant/wesu
  - wequant/cli.py
related_modules:
  - wequant/wefetch/__init__.py
  - wequant/wesu/__init__.py
  - wequant/config.py
  - wequant/mongo.py
related_tables:
  - stock_day
  - future_day
  - stock_adj
  - stock_list
  - future_list
  - etf_list
keywords: [WEFetch, WESU, SSOT, day_frequency, e2e]
---

# WEFetch/WESU 迁移 SSOT
## Final
- 目标：从 QUANTAXIS 的 QAFetch/QASU 抽离 stock/future/ETF 的 MongoDB 读写能力，落地到 `wequant/wefetch` 与 `wequant/wesu`。
- 迁移范围：仅 stock/future/ETF 的 fetch/save/list/adj（含必要的 util/config/mongo）。
- 兼容目标：接口语义与 QUANTAXIS 对齐（字段、日期、行数、幂等）。
- 运行形态：本地 Windows 开发为主；CLI 提供 doctor/init-indexes/smoke-*。

## Contracts
- Fetch API：`docs/DOCS_V2/20_KB/data_layer/KB_data_layer_fetch_api_contract.md`
- Save API：`docs/DOCS_V2/20_KB/data_layer/KB_data_layer_save_api_contract.md`
- Schema/Index：`docs/DOCS_V2/20_KB/data_layer/KB_data_layer_schema_and_indexing.md`
- CLI Contract：`docs/DOCS_V2/20_KB/data_layer/KB_data_layer_cli_contract.md`
- Function Mapping：`docs/DOCS_V2/20_KB/data_layer/KB_data_layer_function_mapping.md`
- ENV：本 Dossier `02_ENV_CONTRACT.md`

## Used Function Inventory (repo scan)
Scope: 全仓扫描 `QAFetch/QASU/QA_fetch_/QA_SU_` 的直接调用点（不含文档）。
- 结果：未发现代码调用；仅文档中存在迁移描述。

## Verification Order
1) `pip install -e .` 可用
2) CLI `wequant doctor` 连接 Mongo 成功
3) WEFetch fetch day/list/adj 正常
4) WESU bulk upsert 幂等
5) e2e：同一 Mongo、同一参数，QUANTAXIS vs WEQUANT 输出一致

## Decisions
- ETF 日线集合选择：默认 `stock_day`（与 QUANTAXIS 代码一致）；若 `WEQUANT_ETF_DAY_COLLECTION` 指定则强制使用；若 `etf_day` 存在且 `stock_day` 未包含 ETF 代码，则切换到 `etf_day`。

## Rollback
- WEFetch/WESU 仅读写 Mongo；回滚=停用 wequant 包，恢复 QUANTAXIS 直接调用。

## Lessons
- Path Contract：绝对路径只允许出现在 `docs/DOCS_V2/99_WORKSPACE.md`
- 写入必须幂等：unique index + bulk upsert
