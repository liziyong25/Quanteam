---
title: WEFetch/WESU Migration - Tasks
kind: dossier
component: data_layer
topics: [tasks, acceptance, migration]
status: draft
created: 2026-02-03
updated: 2026-02-03
source_paths:
  - docs/DOCS_V2/10_DOSSIERS/DOSSIER_20260203_wequant_wefetch_wesu_migration/00_OVERVIEW.md
related_modules: []
related_tables: []
keywords: [Phase0, Phase1, Phase2, e2e]
---

# 03_TASKS
## Phase 0 - DOCS_V2 合规
- [ ] 新建迁移 Dossier（本目录）
- [ ] KB 补齐：Fetch/Save/Schema/CLI/Mapping
- [ ] Index 更新：`03_INDEX/index.json` + `03_INDEX/index_by_recency.md`

## Phase 1 - WEFetch/WESU 迁移
- [ ] WEFetch：stock_day/future_day/etf_day/stock_adj + list
- [ ] WESU：stock_day/future_day/etf_day/stock_adj + list
- [ ] Mongo 索引：unique(code,date) + (code,date_stamp) 非唯一辅助索引
- [ ] CLI：doctor/init-indexes/smoke-fetch/smoke-save

## Phase 2 - e2e 对照
- [ ] e2e 抽样代码（seed+过滤无数据）
- [ ] QUANTAXIS vs WEQUANT fetch 对照（字段/行数/日期）
- [ ] save 幂等：重复写入不增行

## PASS Criteria
- `pip install -e .` OK
- `pytest -q` OK（默认跳过 e2e）
- `WEQUANT_E2E=1 pytest -q` OK
- CLI smoke OK
