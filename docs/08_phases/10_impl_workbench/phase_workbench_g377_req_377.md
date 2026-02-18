# Phase G377: Requirement Gap Closure (WB-053)

## Goal
- Close requirement gap `WB-053` from `docs/00_overview/workbench_ui_productization_v1.md:123`.

## Requirements
- Requirement IDs: WB-053
- Owner Track: impl_workbench
- Clause[WB-053]: 可操作: 草稿编辑并应用、回退上一草稿版本。

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
1. Confirm dependency handoff from `G375` by validating Phase-1 session state artifacts remain stable (`session.json`, `events.jsonl`, route alias precedence) before touching WB-053 behavior.
2. Implement WB-053 draft operations in `src/quant_eam/api/ui_routes.py`:
   - keep editable draft save flow for non-idea steps,
   - apply historical draft deterministically,
   - rollback to previous draft selection deterministically.
3. Preserve deterministic draft snapshot metadata (selected/previous version + hash/path) in session and selected index artifacts so apply/rollback behavior is replay-stable.
4. Expose UI controls in `src/quant_eam/ui/templates/workbench.html` for edit/save/apply/rollback in Phase-1 and keep non-idea-step guardrails.
5. Extend/adjust `tests/test_ui_mvp.py` coverage for:
   - create-idea acceptance path with WB-053 draft lifecycle assertions,
   - path-traversal rejection on draft handlers and wb-053 requirement alias reachability.
6. Update SSOT traceability in `docs/12_workflows/skeleton_ssot_v1.yaml`:
   - register `G377`,
   - map `WB-053 -> G377`,
   - mark requirement implemented with acceptance verified.
7. Acceptance evidence commands:
   - `python3 scripts/check_docs_tree.py`
   - `python3 -m pytest -q tests/test_ui_mvp.py::test_ui_create_idea_job_from_form tests/test_ui_mvp.py::test_path_traversal_blocked`
   - `rg -n "G377|WB-053" docs/12_workflows/skeleton_ssot_v1.yaml`
