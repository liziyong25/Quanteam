# Phase G381: Requirement Gap Closure (WB-056)

## Goal
- Close requirement gap `WB-056` from `docs/00_overview/workbench_ui_productization_v1.md:127`.

## Requirements
- Requirement IDs: WB-056
- Owner Track: impl_workbench
- Clause[WB-056]: 展示卡: K 线叠加卡、trace assertion 卡、fetch evidence 摘要卡、sanity metrics 卡。

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
1. Dependency and contract freeze
   - Confirm `G379` is already `implemented`.
   - Freeze Phase-2 reusable field contract as:
     `calc_trace_preview_path` / `calc_trace_plan_path` / `trace_meta_path` / `fetch_result_meta_path`.
2. Backend `trace_preview` card assembly
   - Keep `WB-045` parent result-card compatibility unchanged.
   - Add explicit `fetch_evidence_summary` structure with:
     `status`, `reason`, `row_count`, `as_of`, `availability`, `no_lookahead`.
   - Emit Phase-2 field-contract rows in card details for deterministic review.
3. `/ui/workbench` Phase-2 rendering
   - Render four explicit cards:
     K-line overlay, trace assertion, fetch evidence summary, sanity metrics.
   - Add empty/error text for missing artifacts or malformed payloads.
4. Route entry and precedence
   - Add `/ui/workbench/req/wb-056`.
   - Keep it registered before `/ui/workbench/{session_id}` to avoid route shadowing.
5. Test coverage
   - Extend `tests/test_ui_mvp.py` route and page assertions for `WB-056`.
   - Add trace-preview payload-shape assertions in `tests/test_ui_workbench_phase_cards_g372.py`.
6. SSOT writeback and acceptance
   - Write `G381|WB-056` trace into `docs/12_workflows/skeleton_ssot_v1.yaml`.
   - Run acceptance commands:
     `python3 scripts/check_docs_tree.py`,
     `python3 -m pytest -q tests/test_ui_mvp.py::test_ui_create_idea_job_from_form tests/test_ui_mvp.py::test_path_traversal_blocked`,
     `rg -n "G381|WB-056" docs/12_workflows/skeleton_ssot_v1.yaml`.
