---
title: WEQUANT DOCS_V2 — Governance (SSOT + Maintenance + Path Contract)
kind: kb
component: docops
topics: [governance, ssot, maintenance, path_contract]
status: stable
created: 2026-02-02
updated: 2026-02-02
source_paths: []
related_modules: []
related_tables: []
keywords: [SSOT, _maint, no_absolute_paths, lanes]
---

# 04_GOVERNANCE（WEQUANT 高层规范）

## 1) Path Contract（硬规则：写错就失败）
- 唯一允许的工作区根路径：见 `99_WORKSPACE.md` 的 `workspace_root_windows`
- 文档中禁止绝对路径（唯一例外：`99_WORKSPACE.md`）
- `source_paths / References / related_modules / Test Plan` 统一使用 repo 相对路径

## 2) SSOT（单一真相）
- 同一主题永远只有 1 份主文档：`10_DOSSIERS/DOSSIER_YYYYMMDD_<topic>/00_OVERVIEW.md`
- SSOT 必须承载：Final / Contracts / Verification / Rollback / Lessons
- 过程型排障写入：`_maint/`

## 3) Lanes（DEV / PROD）
- DEV lane：Windows（研究/开发）
- PROD lane：Linux（未来部署/批跑）
- 一个 Dossier 的验收必须显式写出两条 lane 的命令与 PASS 判据（写入 `05_ACCEPTANCE_EVIDENCE.md`）

## 4) Templates（必须使用）
- `02_TEMPLATES/TEMPLATE_DOSSIER_PACKAGE.md`
- `02_TEMPLATES/TEMPLATE_DATAFLOW_FUNCTION_LEVEL.md`
- `02_TEMPLATES/TEMPLATE_LESSON.md`

## 5) Dataflow Contract（必须有 06_DATAFLOW_FUNCTION_LEVEL + run-backed evidence）
- 每个 Dossier 必须包含 `06_DATAFLOW_FUNCTION_LEVEL.md`
- Evidence 区域必须基于真实运行回填（不允许占位符）
