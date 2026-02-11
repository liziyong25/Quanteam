---
title: WEQUANT data_layer — ENV Contract
kind: dossier
component: data_layer
topics: [env, contract, mongodb]
status: draft
created: 2026-02-02
updated: 2026-02-02
source_paths:
  - wequant/config.py
related_modules:
  - wequant/config.py
related_tables: []
keywords: [WEQUANT_MONGO_URI, WEQUANT_DB_NAME]
---

# 02_ENV_CONTRACT（WEQUANT data_layer）

## Variables

| name | scope | required | default | secret | where_defined | where_used |
|---|---|---:|---|---:|---|---|
| `WEQUANT_MONGO_URI` | runtime | No | `mongodb://localhost:27017` | Yes | OS env / conda activate | `wequant/config.py` |
| `WEQUANT_DB_NAME` | runtime | No | `quantaxis` | No | OS env / conda activate | `wequant/config.py` |

## Build-time vs Runtime
- WEQUANT 是库项目：不定义 build-time env；上述变量均为 runtime。
