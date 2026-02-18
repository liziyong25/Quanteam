# Phase G378: Requirement Gap Closure (WB-054)

## Goal
- Close requirement gap `WB-054` from `docs/00_overview/workbench_ui_productization_v1.md:124`.

## Requirements
- Requirement IDs: WB-054
- Owner Track: impl_workbench
- Clause[WB-054]: 可操作: 草稿编辑并应用、回退上一草稿版本。

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
1. Confirm `G376` output contracts are frozen for Phase‑1 strategy cards and keep `WB-054` implementation strictly scoped to draft edit/apply/rollback.
2. Implement/verify draft edit + apply handlers and UI controls so operations only mutate the addressed step draft store (`draft_vNN` + `selected.json`).
3. Implement/verify rollback-to-previous behavior using `draft_selection_history` + `selection_snapshot` to keep `selected` pointer and history deterministic/idempotent.
4. Harden error/security branches:
   - no rollback history,
   - revision conflict on concurrent edits (`expected_revision`),
   - invalid step/path/version payload rejection.
5. Add `WB-054` requirement entry alias and route-inventory exposure on `/ui/workbench`.
6. Update SSOT traceability (`G378` + `WB-054`) and run acceptance commands:
   - `python3 scripts/check_docs_tree.py`
   - `python3 -m pytest -q tests/test_ui_mvp.py::test_ui_create_idea_job_from_form tests/test_ui_mvp.py::test_path_traversal_blocked`
   - `rg -n "G378|WB-054" docs/12_workflows/skeleton_ssot_v1.yaml`
