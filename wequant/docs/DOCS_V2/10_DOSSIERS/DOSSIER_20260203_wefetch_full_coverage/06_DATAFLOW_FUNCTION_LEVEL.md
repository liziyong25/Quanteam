---
title: WEFetch Full Coverage - Dataflow (Function Level)
kind: dossier
component: data_layer
topics: [dataflow, wefetch, qaquery]
status: draft
created: 2026-02-03
updated: 2026-02-03
source_paths:
  - wequant/wefetch/query.py
  - wequant/wefetch/query_advance.py
related_modules:
  - wequant/datastruct
related_tables: []
keywords: [dataflow, mongo, e2e]
---

# Dataflow (Function Level)
## Part 1: Module-level (Mermaid)
```mermaid
flowchart LR
  A[Caller] --> B[wequant.wefetch.query]
  B --> C[(MongoDB)]
  B --> D[DataFrame]
  A --> E[wequant.wefetch.query_advance]
  E --> B
  E --> F[QA_DataStruct_*]
```

## Part 2: Function-level Flows
- `fetch_*`:
  ???`code/start/end/frequence/collections`
  ???`pd.DataFrame` / list / scalar
  ?????? e2e + notebook ??
- `fetch_*_adv`:
  ????? `fetch_*` ??
  ???`QA_DataStruct_*`?`.data` ? DataFrame?
  ?????? e2e + notebook ??

## Part 3: Minimal Interfaces
- DB: MongoDB collections (? QUANTAXIS ??)
- Library: `wequant.wefetch.query` / `wequant.wefetch.query_advance`
- Consumer: WEFetch API / notebook / e2e tests

## Evidence
- ? `05_ACCEPTANCE_EVIDENCE.md`
