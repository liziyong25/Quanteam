# Phase G368: Requirement Gap Closure (WB-039)

## Goal
- Close requirement gap `WB-039` from `docs/00_overview/workbench_ui_productization_v1.md:107`.
- Scope-lock this phase to the WB-039 data-persistence baseline only.

## Requirements
- Requirement IDs: WB-039
- Owner Track: impl_workbench
- Clause[WB-039]: 用户导向实时策略工作台 UI 改造方案（主控 + Subagent 执行版） / 4.4 数据落盘（新增）

## Non-Goals
- Do not close `WB-040+` in this phase.
- Do not modify WB-038 route/interface behavior (`GET /ui/workbench/{session_id}` and `WORKBENCH_ROUTE_INTERFACE_V43` stay unchanged).
- Do not modify `contracts/**`, `policies/**`, or Holdout visibility scope.

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.
- Bundling criterion: same owner track + same source document + same parent requirement + near-adjacent source lines.

## DoD
- Dependency gate verified: `G367` is implemented and WB-038 route/interface behavior remains unchanged.
- Workbench session flow exposes a stable WB-039 persistence baseline contract for 4.4 paths.
- Session/create/get persistence wiring preserves safe-id/path guarantees for `session_id`, `job_id`, and `step`.
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
1. Dependency gate check:
   - Confirm `G367` is `implemented` in `docs/12_workflows/skeleton_ssot_v1.yaml`.
   - Keep `GET /ui/workbench/{session_id}` behavior and `WORKBENCH_ROUTE_INTERFACE_V43` unchanged.
2. WB-039 persistence baseline hardening in `src/quant_eam/api/ui_routes.py`:
   - Make workbench persistence path wiring explicitly job-bound during session initialization.
   - Publish a stable persistence contract payload for session create/get responses and session document storage.
   - Keep existing artifact path conventions under `artifacts/workbench/sessions/<session_id>/...` and `artifacts/jobs/<job_id>/outputs/workbench/...`.
3. Safety and regression checks in `tests/test_ui_mvp.py`:
   - Verify persistence contract fields exist and remain stable after `POST /workbench/sessions`.
   - Verify persisted session payload contains the same baseline contract.
   - Keep traversal protections and WB-038 route behavior assertions intact.
4. SSOT writeback for `G368` and `WB-039` only, then run acceptance commands:
   - `python3 scripts/check_docs_tree.py`
   - `python3 -m pytest -q tests/test_ui_mvp.py::test_ui_create_idea_job_from_form tests/test_ui_mvp.py::test_path_traversal_blocked`
   - `rg -n "G368|WB-039" docs/12_workflows/skeleton_ssot_v1.yaml`
