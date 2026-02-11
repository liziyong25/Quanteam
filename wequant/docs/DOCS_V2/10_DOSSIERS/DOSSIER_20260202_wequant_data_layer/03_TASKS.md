---
title: WEQUANT data_layer — Tasks
kind: dossier
component: data_layer
topics: [tasks, acceptance, migration]
status: draft
created: 2026-02-02
updated: 2026-02-02
source_paths:
  - docs/DOCS_V2/10_DOSSIERS/DOSSIER_20260202_wequant_data_layer/00_OVERVIEW.md
related_modules: []
related_tables: []
keywords: [Phase0, Phase1, Phase2]
---

# 03_TASKS（WEQUANT data_layer）

## Phase 0（Doc & Repo Foundation）
- [ ] 建立 docs/DOCS_V2 结构（SSOT/Kb/Lessons/Index）
- [ ] 建立 wequant 可安装包（pyproject + import test）
- [ ] 明确 ENV contract（Mongo URI/DB）

## Phase 1（WEFetch/WESU v0：Mongo direct）
- [ ] WEFetch：stock_day/future_day/stock_adj + list collections
- [ ] WESU：对 stock_day/future_day/stock_adj 实现 bulk upsert 幂等写入
- [ ] 最小索引：unique(code,date) 自动创建（写侧）

## Phase 1 Acceptance（DEV lane）
- [ ] `pytest -q` PASS
- [ ] 连接 Mongo 成功，取到至少 1 个 `stock_list` 条目
- [ ] 任意 code+date 抽样：能取到 `stock_day`/`stock_adj`
- [ ] 写入幂等：重复 save 不产生重复行

## Phase 2（对齐 QUANTAXIS 语义）
- [ ] 对齐字段名/类型（date normalize, numeric fields）
- [ ] 补齐 adjust=qfq/hfq（基于 stock_adj）
- [ ] 抽样对比 QUANTAXIS fetch 输出（同区间同 code）

## Lane B：PROD（Linux）
- [ ] 复制 DEV 验收命令到 Linux conda 环境并跑通
