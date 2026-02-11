---
title: WEQUANT DOCS_V2 — Workspace Root (唯一允许的绝对路径)
kind: kb
component: docops
topics: [workspace, path_contract]
status: stable
created: 2026-02-02
updated: 2026-02-02
source_paths: []
related_modules: []
related_tables: []
keywords: [workspace_root_windows, workspace_root_linux]
---

# 99_WORKSPACE（工作区与执行约束：唯一允许绝对路径的位置）

workspace_root_windows: d:\\WEQUANT
workspace_root_linux: /opt/wequant

## Path Contract（硬规则）
- 除本文件外，任何文档禁止出现绝对路径
- 其他文档引用来源/代码位置时：只写 repo 相对路径，例如：
  - `wequant/wefetch/stock.py`
  - `docs/DOCS_V2/10_DOSSIERS/...`

## Lanes
- DEV lane：Windows（无 docker 也可）
- PROD lane：Linux（后续可上 docker/compose，但当前不要求）

## Gate（建议落盘前执行）
- 全局搜索 Windows 盘符路径：除本文件外应为 0
