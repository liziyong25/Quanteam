# Phase G356: Requirement Gap Closure (WB-010)

## Goal
- Close requirement gap `WB-010` from `docs/00_overview/workbench_ui_productization_v1.md:60`.

## Requirements
- Requirement IDs: WB-010
- Owner Track: impl_workbench
- Clause[WB-010]: 用户导向实时策略工作台 UI 改造方案（主控 + Subagent 执行版） / 3.2 核心功能需求（FR）

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.
- Bundling criterion: same owner track + same source document + same parent requirement + near-adjacent source lines.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Scope boundary
- 本目标仅闭环父需求 `WB-010`（`3.2 核心功能需求（FR）`），只更新其状态与 SSOT 映射关系。
- `WB-011` ~ `WB-020` 仅保留为已规划子需求，不得在本目标内标记 `implemented`。
- 路由、持久化、UI 运行时实现和治理规则变更不在本文件的可交付范围内，仅聚焦于目标-SSOT 回写闭环与边界锚定。

## Implementation Plan
1. 依赖门确认（执行前检查）
   - 在 `docs/12_workflows/skeleton_ssot_v1.yaml` 验证 `G354` 已为 `status_now: implemented` 且 `acceptance_verified: true`，并记录验收时间戳。
2. 范围锚定（避免子 FR 溢出）
   - 以 `docs/00_overview/workbench_ui_productization_v1.md:60` 定位 `WB-010` 父需求行。
   - 明确 `WB-011`~`WB-020` 保持 `planned`，仅作为 `WB-010` 子树，不执行闭环/实现状态迁移。
3. SSOT 目标闭环补齐
   - 确认 `goal_checklist` 中 `G356` 的 `track=impl_workbench`、`depends_on: [G354]`、`requirement_ids: [WB-010]`、`phase_doc_path` 与允许路径边界准确存在。
   - 按 `requirements` 与 `acceptance_commands` 写法对齐到统一格式，避免后续证据检索歧义。
4. Trace 与状态对齐
   - 更新 `requirements_trace_v1` 的 `WB-010`：
     - `mapped_goal_ids` 包含 `G356`。
     - 附加本目标验收命令。
     - `status_now` 与 `acceptance_verified` 延迟更新，待验收命令通过后再翻转。
5. 验收命令与 OR 风险核验
   - 按顺序执行：
     - `python3 scripts/check_docs_tree.py`
     - `python3 -m pytest -q tests/test_ui_mvp.py::test_ui_create_idea_job_from_form tests/test_ui_mvp.py::test_path_traversal_blocked`
     - `rg -n "G356|WB-010" docs/12_workflows/skeleton_ssot_v1.yaml`
   - 对最后的 `rg` 结果做双重核对：既要看到 `G356`，也要看到 `WB-010`，避免 OR 命中掩盖缺失。

## Required skills
- requirement-splitter
- ssot-goal-planner
- phase-authoring
- packet-evidence-guard
