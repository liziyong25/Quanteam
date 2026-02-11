---
title: WEQUANT DOCS_V2 — Taxonomy
kind: kb
component: docops
topics: [taxonomy, naming, lifecycle]
status: draft
created: 2026-02-02
updated: 2026-02-02
source_paths: []
related_modules: []
related_tables: []
keywords: [components, topics, status, ssot]
---

# 01_TAXONOMY（WEQUANT）

## Components（组件枚举）
- `data_layer`：数据层（MongoDB access, WEFetch/WESU）
- `backtest`：回测层（vectorbt 集成与规范）
- `devops`：环境与打包（conda/pip, Windows/Linux lanes）
- `docops`：DOCS_V2 文档体系本身
- `calc`：指标/特征/统计计算（后续扩展）

## Naming（命名规范，遵循 DOCS_V2）
- 入口文件：`00_*.md`
- Dossier 目录：`10_DOSSIERS/DOSSIER_YYYYMMDD_<topic_slug>/`
- Dossier 文件集（最小）：`00_OVERVIEW.md` / `02_ENV_CONTRACT.md` / `03_TASKS.md` / `05_ACCEPTANCE_EVIDENCE.md` / `06_DATAFLOW_FUNCTION_LEVEL.md`
- KB：`20_KB/<component>/KB_<component>_<topic>.md`
- Lesson：`30_LESSONS/LESSON_YYYYMMDD_<scope>_<short-title>.md`

## Status（状态流转）
- `draft`：讨论/快速迭代
- `stable`：接口/规则稳定；修改必须带 changelog（Dossier 或 KB 内）
- `deprecated`：被替代；必须写迁移路径
