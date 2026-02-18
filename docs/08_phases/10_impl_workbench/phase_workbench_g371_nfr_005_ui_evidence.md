# Phase G371: Requirement Gap Closure (WB-026)

## Goal
- Close requirement gap `WB-026` from `docs/00_overview/workbench_ui_productization_v1.md:78`.

## Requirements
- Requirement IDs: WB-026
- Owner Track: impl_workbench
- Clause[WB-026]: NFR-005 全链路错误可解释（UI 给出可读失败原因 + evidence 引用）。

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.
- Bundling criterion: same owner track + same source document + same parent requirement + near-adjacent source lines.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Dependency Validation (G358)
- Confirm `G358` is already `implemented` in SSOT and treat existing workbench route/schema contracts as frozen baseline.
- Keep changes additive and localized to failure explainability; no route removals and no holdout/contracts/policies scope drift.

## Scope Guard
- This phase closes only `WB-026`.
- Do not modify `contracts/**`, `policies/**`, or expand Holdout visibility.
- Keep all edits within goal `allowed_paths`.

## Implementation Plan
1. Normalize WB-026 failure context in Workbench API:
   - Add one reusable failure context model (`failure_reason`, readable message, event link, evidence refs).
   - Persist `last_failure` in session payload for UI consumption.
2. Wire failure explainability across real error paths:
   - Workbench create (real-jobs path) degraded fetch failure.
   - Fetch-probe runtime failure.
   - Step-rerun failure.
3. Render WB-026 UI evidence:
   - Add a session-level “Failure Explainability (WB-026)” section.
   - Include explicit evidence refs and fetch error evidence path on `/ui/workbench/{session_id}`.
4. Add focused test coverage:
   - Assert rerun and fetch-probe failures expose readable reasons + evidence refs.
   - Assert failure context is persisted and visible on the UI page.
5. Write SSOT goal/requirement updates:
   - Mark `WB-026` implemented and map to `G371`.
   - Register cluster metadata for `CL_FETCH_371`.

## Implemented Changes
- `src/quant_eam/api/ui_routes.py`
  - Added WB-026 failure context helpers and session persistence fields (`last_failure`, `fetch_probe_error_ref`).
  - Added failure capture + evidence refs on create degraded fetch, fetch-probe error, and rerun failure.
  - Added structured failure payload in fetch-probe error responses and rerun HTTP error detail.
- `src/quant_eam/ui/templates/workbench.html`
  - Added “Failure Explainability (WB-026)” render block with readable reason and evidence refs.
  - Added fetch error evidence path rendering near Phase-0 fetch preview status.
- `tests/test_ui_workbench_sessions_g365.py`
  - Extended rerun failure test with failure-context payload assertions and UI render assertions.
- `tests/test_ui_workbench_sessions_g366.py`
  - Added fetch-probe failure regression test for readable failure reason + evidence refs + UI visibility.
- `docs/12_workflows/skeleton_ssot_v1.yaml`
  - Added `G371`, mapped `WB-026` to implemented, and registered `CL_FETCH_371`.

## Acceptance Evidence
- Required acceptance command outputs are recorded in:
  - `artifacts/subagent_control/G371/acceptance_run_log.jsonl`

## Acceptance Run (Executed)
- `python3 scripts/check_docs_tree.py` -> `docs tree: OK`
- `python3 -m pytest -q tests/test_ui_mvp.py::test_ui_create_idea_job_from_form tests/test_ui_mvp.py::test_path_traversal_blocked` -> `2 passed`
- `rg -n "G371|WB-026" docs/12_workflows/skeleton_ssot_v1.yaml` -> matched goal, requirement, and cluster markers for `G371/WB-026`.
