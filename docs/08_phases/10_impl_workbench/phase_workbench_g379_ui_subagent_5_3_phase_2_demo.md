# Phase G379: Requirement Gap Closure (WB-055)

## Goal
- Close requirement gap `WB-055` from `docs/00_overview/workbench_ui_productization_v1.md:126`.

## Requirements
- Requirement IDs: WB-055
- Owner Track: impl_workbench
- Clause[WB-055]: 用户导向实时策略工作台 UI 改造方案（主控 + Subagent 执行版） / 5.3 Phase‑2（Demo 验证）

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
1. Dependency gate on `G378`:
   - Re-confirm Phase-1 reusable contract fields stay unchanged for handoff: `current_step`, `step_index`, `job_checkpoint`, `drafts`, `draft_selection_history`, `draft_selection_snapshots`.
   - Keep `WB-055` scope locked to Phase-2 skeleton handoff/evidence only; do not include `WB-056` card-detail expansion or `WB-057` rollback/rerun controls.
2. Implement WB-055 Phase-2 skeleton behavior in `src/quant_eam/api/ui_routes.py`:
   - On real-jobs `POST /workbench/sessions/{session_id}/continue`, when workflow reaches `trace_preview`, emit deterministic checkpoint evidence file:
     `jobs/<job_id>/outputs/workbench/phase2_trace_preview_checkpoint.json`.
   - Require checkpoint evidence to include `WAITING_APPROVAL(step=trace_preview)` presence/offset, and persist summary in session state as `phase2_checkpoint`.
   - Attach `phase2_checkpoint` into card detail payload for traceability.
3. Add requirement entry route alias for WB-055 with precedence safety:
   - Register `GET|HEAD /ui/workbench/req/wb-055` before `/ui/workbench/{session_id}`.
   - Update workbench requirement-entry alias inventory and UI route catalog mapping.
4. Targeted regression coverage in `tests/test_ui_mvp.py`:
   - Validate `/ui/workbench/req/wb-055` is reachable and ordered before dynamic session route.
   - Add real-jobs WB-055 flow assertion: continue reaches `trace_preview` and checkpoint evidence confirms stable `WAITING_APPROVAL(step=trace_preview)`.
5. Update SSOT traceability (`docs/12_workflows/skeleton_ssot_v1.yaml`):
   - Add goal node `G379` and map `WB-055 -> implemented`.
   - Update related capability cluster and latest phase pointers for the impl_workbench chain.
6. Acceptance evidence commands:
   - `python3 scripts/check_docs_tree.py`
   - `python3 -m pytest -q tests/test_ui_mvp.py::test_ui_create_idea_job_from_form tests/test_ui_mvp.py::test_path_traversal_blocked`
   - `rg -n "G379|WB-055" docs/12_workflows/skeleton_ssot_v1.yaml`
