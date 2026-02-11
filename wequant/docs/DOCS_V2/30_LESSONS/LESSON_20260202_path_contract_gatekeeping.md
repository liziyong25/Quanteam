---
title: LESSON_20260202_path_contract_gatekeeping
kind: lesson
component: docops
topics: [lessons, path_contract]
status: stable
created: 2026-02-02
updated: 2026-02-02
source_paths:
  - docs/DOCS_V2/99_WORKSPACE.md
  - docs/DOCS_V2/04_GOVERNANCE.md
related_modules: []
related_tables: []
keywords: [no_absolute_paths]
---

# Path Contract Gatekeeping

## Symptoms
- 文档中出现 Windows 盘符绝对路径，导致跨环境引用失败（Windows/Linus 不一致）。
- AI/人类在说明命令时把本机路径写死，后续维护不可复现。

## Root Cause
- 未建立“唯一允许绝对路径的位置”，导致路径散落在多处。

## Fix
- 绝对路径只允许出现在 `docs/DOCS_V2/99_WORKSPACE.md`。
- 其他文档统一使用 repo 相对路径。

## Verification
- 全局搜索 Windows 盘符路径：除 `99_WORKSPACE.md` 外命中=0。

## Preventive Action
- 每次新增/修改文档前做 scoped 自检（仅本次变更文件）。
