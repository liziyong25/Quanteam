---
title: WEFetch/WESU Migration - ENV Contract
kind: dossier
component: data_layer
topics: [env, mongodb, contracts]
status: draft
created: 2026-02-03
updated: 2026-02-03
source_paths:
  - wequant/config.py
  - wequant/mongo.py
related_modules: []
related_tables: []
keywords: [WEQUANT_MONGO_URI, WEQUANT_DB_NAME, WEQUANT_ETF_DAY_COLLECTION]
---

# ENV Contract
## Mongo
- `WEQUANT_MONGO_URI`: MongoDB 连接串（默认 `mongodb://localhost:27017`）
- `WEQUANT_DB_NAME`: 目标数据库名（默认 `quantaxis`）

## ETF 日线集合选择
- `WEQUANT_ETF_DAY_COLLECTION`: 若设置，强制 ETF 日线读取/写入该集合

## e2e
- `WEQUANT_E2E=1`: 启用 e2e 测试
- `WEQUANT_E2E_SAMPLE_SIZE`: e2e 抽样 size（默认 3）
- `WEQUANT_E2E_SEED`: e2e 抽样 seed（默认 20250101）
- `WEQUANT_QA_PATH`: QUANTAXIS 源码路径（用于对照测试）
