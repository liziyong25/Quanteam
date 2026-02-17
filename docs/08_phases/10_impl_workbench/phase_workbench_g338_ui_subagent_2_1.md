# Phase G338: Requirement Gap Closure (WB-001)

## Goal
- 把 `docs/00_overview/workbench_ui_productization_v1.md:16` 的 `WB-001` 细化成可执行主控与 Subagent 任务，并完成最小闭环实现和追踪链路落地。

## Requirements
- Requirement IDs: `WB-001`
- Owner Track: `impl_workbench`
- Clause[WB-001]: `用户导向实时策略工作台 UI 改造方案（主控 + Subagent 执行版） / 2.1 产品目标`
- Scope boundary: 本阶段为工作台改造基线闭环，禁止修改 `contracts/**`、`/ui/jobs` / `/ui/runs` 既有行为约束。

## Architecture
- 工作台会话层（Workbench）与现有内核解耦，仅提供：
  - API：`/workbench/sessions*` 与 `events` 查询
  - Session 持久化：`artifacts/workbench/sessions/<session_id>/session.json`
  - 事件日志：`artifacts/workbench/sessions/<session_id>/events.jsonl`
- UI: `/ui/workbench` 入口页与 `/ui/workbench/{session_id}` 会话页，采用 read-only 展示 + 可追溯引用（不新增外部依赖）。
- 关键对齐来源：
  - `docs/00_overview/workbench_ui_productization_v1.md`
  - `docs/12_workflows/skeleton_ssot_v1.yaml`
  - 既有 UI 路由/证据清单路径

## DoD
- 追踪与文档闭环：
  - 本阶段新增/更新文件包含 `G338` / `WB-001` 可追溯标识。
  - `docs/12_workflows/skeleton_ssot_v1.yaml` 同步写入目标 Goal 与 Requirement 绑定。
- 主控执行清单：
  - 明确 `/ui/workbench` 页面与 `/workbench/sessions*` API 的最小可操作契约。
  - 保证 `/workbench/sessions` 默认行为为 append-only 会话创建。
- 验收命令：
  - `python3 scripts/check_docs_tree.py`
  - `python3 -m pytest -q tests/test_ui_mvp.py`
  - `rg -n "G338|WB-001" docs/12_workflows/skeleton_ssot_v1.yaml`

## Implementation Plan
- 主控清单（按顺序执行）：
  - 先在 `src/quant_eam/api/ui_routes.py` 增加 `/workbench/sessions*` API 与 `/ui/workbench*` 页面端点；
  - 后在 `src/quant_eam/ui/templates/workbench.html` 与 `base.html` 补充入口和文案；
  - 再在 `docs/12_workflows/skeleton_ssot_v1.yaml` 补齐 `G338` goal 与 `WB-001` 映射；
  - 最后补齐当前 phase 文档与可追溯性条目。
- Subagent 建议分工（并行）：
  - Subagent-A：API 路由、会话存储、事件/草稿落盘。
  - Subagent-B：UI 页面、导航入口、可视化状态页。
  - Subagent-C：SSOT 写回与 requirements_trace 绑定校验。
- Subagent 汇总与验收：由主控统一执行交付命令并回写。

TBD by controller at execution time.
