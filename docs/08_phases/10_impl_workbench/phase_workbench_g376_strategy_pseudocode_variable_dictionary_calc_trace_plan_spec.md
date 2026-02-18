# Phase G376: Requirement Gap Closure (WB-052)

## Goal
- Close requirement gap `WB-052` from `docs/00_overview/workbench_ui_productization_v1.md:122`.

## Requirements
- Requirement IDs: WB-052
- Owner Track: impl_workbench
- Clause[WB-052]: 展示卡: strategy_pseudocode 卡、variable_dictionary 摘要卡、calc_trace_plan 摘要卡、Spec-QA 风险卡。

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
1. Validate G375 dependency handoff by confirming Phase-1 data-contract fields (`signal_dsl_path`, `variable_dictionary_path`, `calc_trace_plan_path`, `spec_qa_report_path`) are consumed through deterministic mapping in workbench UI aggregation.
2. Implement WB-052 strategy-stage card payload mapping in `src/quant_eam/api/ui_routes.py` for:
   - `strategy_pseudocode` card
   - `variable_dictionary` summary card
   - `calc_trace_plan` summary card
   - `Spec-QA` risk card
3. Add explicit `ready/missing/error` status handling per card so missing files or invalid JSON produce readable fallback states instead of silent empty sections.
4. Render WB-052 card blocks and status/fallback UI in `src/quant_eam/ui/templates/workbench.html`, preserving deterministic card order from productization requirement line 122.
5. Add/update targeted UI regression checks in `tests/test_ui_mvp.py` for WB-052 payload mapping and page-level rendering markers.
6. Write SSOT traceability updates in `docs/12_workflows/skeleton_ssot_v1.yaml` for goal `G376` and requirement `WB-052`, then run acceptance commands:
   - `python3 scripts/check_docs_tree.py`
   - `python3 -m pytest -q tests/test_ui_mvp.py::test_ui_create_idea_job_from_form tests/test_ui_mvp.py::test_path_traversal_blocked`
   - `rg -n "G376|WB-052" docs/12_workflows/skeleton_ssot_v1.yaml`
