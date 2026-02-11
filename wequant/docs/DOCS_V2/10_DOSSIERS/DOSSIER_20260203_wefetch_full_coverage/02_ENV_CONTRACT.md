---
title: WEFetch Full Coverage - ENV Contract
kind: dossier
component: data_layer
topics: [env, mongodb, e2e]
status: draft
created: 2026-02-03
updated: 2026-02-03
source_paths:
  - wequant/config.py
  - wequant/mongo.py
related_modules: []
related_tables: []
keywords: [WEQUANT_MONGO_URI, WEQUANT_DB_NAME, WEQUANT_QA_PATH]
---

# ENV Contract
- `WEQUANT_MONGO_URI`: MongoDB ?????? `mongodb://localhost:27017`?
- `WEQUANT_DB_NAME`: MongoDB ??????? `quantaxis`?
- `WEQUANT_QA_PATH`: QUANTAXIS ??????? e2e ?? import?
- `WEQUANT_E2E`: e2e ???`1` ????????
- `WEQUANT_E2E_SAMPLE_SIZE`: ??????? 3?
- `WEQUANT_E2E_SEED`: ????????? 20250101?
- `WEQUANT_ETF_DAY_COLLECTION`: ETF ?? collection ??????
