# Phase G359: Requirement Gap Closure (WB-027)

## Goal
- Close requirement gap `WB-027` from `docs/00_overview/workbench_ui_productization_v1.md:90`.
- Implement and harden only the two stores required by `WB-027`: Session Store and Step Draft Store.

## Dependency Gate (G358)
- `G358` is already implemented in SSOT (`docs/12_workflows/skeleton_ssot_v1.yaml`) and is treated as the frozen baseline.
- Contract freeze for this phase:
  - Keep existing route surface unchanged:
    - `POST /workbench/sessions`
    - `GET /workbench/sessions/{session_id}`
    - `POST /workbench/sessions/{session_id}/continue`
    - `GET /workbench/sessions/{session_id}/events`
    - `POST /workbench/sessions/{session_id}/steps/{step}/drafts`
    - `POST /workbench/sessions/{session_id}/steps/{step}/drafts/{version}/apply`
  - Keep existing response keys for create/continue/draft/apply flows (additive-only internal hardening).

## Requirements
- Requirement IDs: `WB-027` only
- Owner Track: `impl_workbench`
- Clause[WB-027]: 新增 Session Store 与 Step Draft Store。

## Scope Guard
- In-scope: persistence paths, ownership, safe pathing, deterministic write semantics for Session Store + Step Draft Store.
- Out-of-scope: `WB-028+`, contracts/policies, Holdout visibility expansion.
- Scope anchor for this phase is this document (`phase_workbench_g359_session_store_step_draft_store.md`) only.

## Architecture
- Single SSOT source: `docs/12_workflows/skeleton_ssot_v1.yaml`.
- Session Store (owned by `src/quant_eam/api/ui_routes.py`):
  - `artifacts/workbench/sessions/<session_id>/session.json`
  - `artifacts/workbench/sessions/<session_id>/events.jsonl`
- Step Draft Store (owned by `src/quant_eam/api/ui_routes.py`):
  - `artifacts/jobs/<job_id>/outputs/workbench/step_drafts/<step>/draft_vNN.json`
  - `artifacts/jobs/<job_id>/outputs/workbench/step_drafts/<step>/selected.json`
- Hardening constraints:
  - `session_id`/`step`/`job_id` use safe-id validation before path construction.
  - Child directory joins use direct-child guards.
  - JSON and JSONL writes keep deterministic key ordering.
  - Event append and draft version selection use lock-guarded critical sections to reduce write races.

## DoD
- `WB-027` is mapped to `G359` and marked implemented in SSOT, while downstream `WB-028+` stays unchanged.
- Session create/continue/draft/apply flows continue to pass targeted regression tests without response-shape drift.
- Acceptance commands pass:
  - `python3 scripts/check_docs_tree.py`
  - `python3 -m pytest -q tests/test_ui_mvp.py::test_ui_create_idea_job_from_form tests/test_ui_mvp.py::test_path_traversal_blocked`
  - `rg -n "G359|WB-027" docs/12_workflows/skeleton_ssot_v1.yaml`

## Implementation Plan
1. Freeze the `G358` API/UI contract surface and verify no incompatible route or response changes are introduced.
2. Harden Session Store pathing/writes in `ui_routes.py` for safe identifiers and deterministic persistence.
3. Harden Step Draft Store pathing/writes in `ui_routes.py` for safe identifiers, deterministic versioning, and selected pointer persistence.
4. Validate create/continue/draft/apply flows against existing tests and workbench chain behavior.
5. Write SSOT updates for `G359` + `WB-027` only, preserving status/mappings for unrelated requirements.
6. Record command evidence under `artifacts/subagent_control/G359/`.
