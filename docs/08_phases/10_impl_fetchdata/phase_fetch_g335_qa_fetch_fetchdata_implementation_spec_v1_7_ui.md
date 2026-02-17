# Phase G335: Requirement Gap Closure (QF-093)

## Goal
- Close requirement gap `QF-093` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:174`.

## Requirements
- Requirement IDs: QF-093
- Owner Track: impl_fetchdata
- Clause[QF-093]: QA‑Fetch FetchData Implementation Spec (v1) / 7. UI 集成要求（Review & Rollback） / 7.2 审阅点与回退

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
1. Parse `QF-093` (source line 174) into concrete review/rollback acceptance criteria:
   - Review checkpoint must persist user decision and transition state for resume/retry.
   - Reject path must rollback to the previous checkpoint and allow `fetch_request` edit or rerun.
2. Validate review action handling end-to-end (approve flow):
   - `approve → next stage` transition is wired through runtime + UI integration state.
3. Validate reject action handling end-to-end:
   - `reject → rollback` transition is triggered and attempt history remains append-only.
4. Verify evidence immutability after review interaction:
   - historical attempts remain present and unchanged after reject/retry.
5. Align acceptance:
   - Ensure `docs/12_workflows/skeleton_ssot_v1.yaml` maps `QF-093` to `G335` and `QF-094..QF-096` also to `G335`.
   - Ensure execution checks pass:
     - `python3 scripts/check_docs_tree.py`
     - `python3 -m pytest -q tests/test_qa_fetch_runtime.py`
     - `rg -n "G335|QF-093" docs/12_workflows/skeleton_ssot_v1.yaml`
