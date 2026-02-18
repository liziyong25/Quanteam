# Phase G387: Requirement Gap Closure (WB-065)

## Goal
- Close requirement gap `WB-065` from `docs/00_overview/workbench_ui_productization_v1.md:181`.

## Requirements
- Requirement IDs: WB-065
- Owner Track: impl_workbench
- Clause[WB-065]: 用户导向实时策略工作台 UI 改造方案（主控 + Subagent 执行版） / 8. 验收标准（DoD）

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.
- Bundling criterion: same owner track + same source document + same parent requirement + near-adjacent source lines.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
1. Gate on dependency `G386` before WB-065 edits.
   - Confirm `WB-064` remains implemented in SSOT and verify `/ui/workbench/req/wb-064` plus `workbench_session_store_contract_v1` boundary are stable.
   - Evidence paths: `docs/12_workflows/skeleton_ssot_v1.yaml`, `src/quant_eam/api/ui_routes.py`, `tests/test_ui_mvp.py`.
2. Add WB-065 requirement entry alias without widening state-machine behavior.
   - Wire `/ui/workbench/req/wb-065` in `IA_ROUTE_VIEW_CATALOG`, `WORKBENCH_REQUIREMENT_ENTRY_ALIASES`, and add a dedicated `GET|HEAD` handler before `/ui/workbench/{session_id}`.
   - Evidence paths: `src/quant_eam/api/ui_routes.py`, `tests/test_ui_mvp.py`.
3. Add a WB-065 DoD baseline marker in Workbench UI.
   - Render a static WB-065 card that anchors DoD baseline intent while preserving existing WB-064 contract markers.
   - Evidence paths: `src/quant_eam/ui/templates/workbench.html`, `tests/test_ui_mvp.py`.
4. Lock scope and defer downstream direct closure.
   - Explicitly defer WB-066, WB-067, WB-068, WB-069, WB-070, WB-071, and WB-072 to follow-up goals; G387 only anchors WB-065 DoD baseline.
   - Evidence paths: `src/quant_eam/ui/templates/workbench.html`, `docs/12_workflows/skeleton_ssot_v1.yaml`.
5. Write back SSOT traceability for `G387 <-> WB-065`.
   - Add/refresh the `G387` goal block, map `WB-065` to implemented, and assign the fetch capability cluster linkage.
   - Evidence path: `docs/12_workflows/skeleton_ssot_v1.yaml`.
6. Run acceptance commands.
   - `python3 scripts/check_docs_tree.py`
   - `python3 -m pytest -q tests/test_ui_mvp.py::test_ui_create_idea_job_from_form tests/test_ui_mvp.py::test_path_traversal_blocked`
   - `rg -n "G387|WB-065" docs/12_workflows/skeleton_ssot_v1.yaml`
   - Evidence paths: `artifacts/subagent_control/G387/acceptance_run_log.jsonl`, `artifacts/subagent_control/G387/workspace_after.json`.
