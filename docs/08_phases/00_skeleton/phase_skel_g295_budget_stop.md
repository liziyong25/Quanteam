# Phase G295: Requirement Gap Closure (WV-052)

## Goal
- Close requirement gap `WV-052` from `Quant‑EAM Whole View Framework.md（v0.5‑draft）.md:234`.

## Requirements
- Requirement IDs: WV-052
- Owner Track: skeleton
- Clause[WV-052]: budget_stop（预算/停止条件）

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
1. Validate dependency gate in `docs/12_workflows/skeleton_ssot_v1.yaml`:
   - `G289.status_now == implemented`
   - `WV-044.status_now == implemented` and `WV-044.acceptance_verified == true`
2. Confirm/maintain `G295` goal metadata in SSOT:
   - `track: skeleton`
   - `depends_on: [G289]`
   - `requirement_ids: [WV-052]`
   - `phase_doc_path: docs/08_phases/00_skeleton/phase_skel_g295_budget_stop.md`
3. Confirm/maintain `requirements_trace_v1` linkage for `WV-052`:
   - `source_document: Quant‑EAM Whole View Framework.md（v0.5‑draft）.md`
   - `source_line: 234`
   - `clause: budget_stop（预算/停止条件）`
   - `mapped_goal_ids` includes `G295`
4. Set closure fields consistently after validation:
   - `G295.status_now: implemented`
   - `WV-052.status_now: implemented`
   - `WV-052.acceptance_verified: true`
5. Run acceptance checks:
   - `python3 scripts/check_docs_tree.py`
   - `rg -n "G295|WV-052" docs/12_workflows/skeleton_ssot_v1.yaml`
