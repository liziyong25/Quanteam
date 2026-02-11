---
title: WEQUANT Dev Rules (SSOT) — Workspace + Path Contract + Dossier Discipline
kind: kb
component: docops
topics: [dev_rules, ssot, workspace, path_contract, lanes]
status: stable
created: 2026-02-02
updated: 2026-02-02
source_paths: []
related_modules: []
related_tables: []
keywords: [dossier, lanes, workspace_root_windows]
---

# WEQUANT 开发总规则（SSOT）

开工必读：
- `docs/DOCS_V2/04_GOVERNANCE.md`
- `docs/DOCS_V2/99_WORKSPACE.md`

## 1) Path Contract
- 除 `99_WORKSPACE.md` 外，任何文档禁止绝对路径
- 引用统一使用 repo 相对路径

## 2) Dossier Discipline（每个主题必须可执行）
- 每个主题（需求/重构/拆分）必须落到 1 个 Dossier：
  - `00_OVERVIEW.md`（Final/Contracts/Rollback/Lessons）
  - `03_TASKS.md`（可执行任务 + PASS 判据）
  - `05_ACCEPTANCE_EVIDENCE.md`（命令 + 输出片段）
  - `06_DATAFLOW_FUNCTION_LEVEL.md`（函数级数据流 + evidence）

## 3) Lanes（DEV / PROD）
- DEV lane：Windows（研究/开发）
- PROD lane：Linux（未来部署/批跑）
- 每个 Dossier 必须给出两条 lane 的验收命令（哪怕 PROD 暂时标记为 N/A，也必须写清触发条件与后续补齐计划）

## 4) 禁止“只写叙事”
- Evidence 不允许占位符（例如 TBD/TODO/PLACEHOLDER）
- 未跑通就不允许标记 PASS
