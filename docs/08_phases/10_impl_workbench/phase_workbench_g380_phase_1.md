# Phase G380: Requirement Gap Closure (WB-057)

## Goal
- Close requirement gap `WB-057` from `docs/00_overview/workbench_ui_productization_v1.md:128`.

## Requirements
- Requirement IDs: WB-057
- Owner Track: impl_workbench
- Clause[WB-057]: 可操作: 不通过时回退到 Phase‑1 并重跑。

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
1. Validate dependency baseline from `G379`:
   - Re-run targeted WB-055 acceptance checks to confirm Phase-2 (`trace_preview`) checkpoint behavior remains stable before WB-057 edits.
   - Keep scope locked to WB-057 only; do not absorb WB-056/WB-058 work.
2. Implement Phase-2 rollback+rerun action in `src/quant_eam/api/ui_routes.py`:
   - Add `POST /workbench/sessions/{session_id}/phase2/rollback-rerun`.
   - Require `current_step=trace_preview`; otherwise reject with deterministic `409`.
   - Restore Phase-1 (`strategy_spec`) draft selection using existing draft/version helpers so selected pointers and snapshots remain append-only and safe.
   - Transition session state back to Phase-1 with explicit rollback reason `demo_failed_rollback_to_phase1`, and persist rollback context in session evidence.
   - Trigger rerun from restored Phase-1 draft in the same action and keep existing path-safety helpers unchanged.
3. Implement WB-057 UI/request entry updates:
   - Add `GET|HEAD /ui/workbench/req/wb-057` alias route and keep it registered before `/ui/workbench/{session_id}`.
   - Add UI action button “Rollback To Phase-1 And Rerun” on Phase-2 session view, wired to the new endpoint.
4. Add regression coverage in `tests/test_ui_mvp.py`:
   - Assert `/ui/workbench/req/wb-057` entry is reachable and route precedence remains correct.
   - Assert rollback+rerun flow restores Phase-1 draft version pointers and rerun step starts from `strategy_spec`.
5. Update SSOT writeback in `docs/12_workflows/skeleton_ssot_v1.yaml`:
   - Add implemented goal node `G380` mapped to `WB-057`, with `depends_on: [G379]`.
   - Mark requirement trace `WB-057` as implemented and map to `G380`.
6. Run acceptance bundle and evidence checks:
   - `python3 scripts/check_docs_tree.py`
   - `python3 -m pytest -q tests/test_ui_mvp.py::test_ui_create_idea_job_from_form tests/test_ui_mvp.py::test_path_traversal_blocked`
   - `rg -n "G380|WB-057" docs/12_workflows/skeleton_ssot_v1.yaml`
