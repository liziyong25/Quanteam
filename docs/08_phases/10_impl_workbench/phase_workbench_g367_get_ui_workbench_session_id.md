# Phase G367: Requirement Gap Closure (WB-038)

## Goal
- Close requirement gap `WB-038` from `docs/00_overview/workbench_ui_productization_v1.md:105`.
- Scope-lock this phase to `GET /ui/workbench/{session_id}` only.

## Requirements
- Requirement IDs: WB-038
- Owner Track: impl_workbench
- Clause[WB-038]: GET /ui/workbench/{session_id}

## Non-Goals
- Do not close `WB-039+` in this phase.
- Do not modify WB-028 route/interface contract (`WORKBENCH_ROUTE_INTERFACE_V43`).
- Do not change `contracts/**`, `policies/**`, or Holdout visibility scope.

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.
- Bundling criterion: same owner track + same source document + same parent requirement + near-adjacent source lines.

## DoD
- Dependency gate verified: `G360` is implemented and `WORKBENCH_ROUTE_INTERFACE_V43` remains unchanged.
- `GET|HEAD /ui/workbench/{session_id}` enforces `require_safe_id(session_id)` and renders `workbench.html` with `selected_session`.
- Existing/missing/invalid session-id cases return controlled `200/404/400` (and corrupt payload `409`) without traversal regression.
- Route precedence remains safe: `/ui/workbench` and `/ui/workbench/req/*` are not shadowed by `/ui/workbench/{session_id}`.
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
1. Validate dependency gate and contract freeze:
   - Confirm `G360` is `implemented` in SSOT.
   - Keep `WORKBENCH_ROUTE_INTERFACE_V43` constant unchanged.
2. Harden and verify session UI route in `src/quant_eam/api/ui_routes.py`:
   - Keep `require_safe_id(session_id)` at route entry.
   - Render `workbench.html` using `_workbench_index_context()` plus `selected_session = _workbench_session_context(session_id)`.
   - Preserve controlled HTTP outcomes for missing/invalid/corrupt session artifacts (`404/400/409`).
3. Add focused UI tests in `tests/test_ui_mvp.py`:
   - Session page success after session creation with `selected_session` markers.
   - Invalid-id, missing-session, and corrupt-session assertions.
   - Route-order/precedence checks so `/ui/workbench` and `/ui/workbench/req/*` remain higher-priority than dynamic session route.
4. Write SSOT updates for `G367` and `WB-038` only, then run acceptance commands:
   - `python3 scripts/check_docs_tree.py`
   - `python3 -m pytest -q tests/test_ui_mvp.py::test_ui_create_idea_job_from_form tests/test_ui_mvp.py::test_path_traversal_blocked`
   - `rg -n "G367|WB-038" docs/12_workflows/skeleton_ssot_v1.yaml`
