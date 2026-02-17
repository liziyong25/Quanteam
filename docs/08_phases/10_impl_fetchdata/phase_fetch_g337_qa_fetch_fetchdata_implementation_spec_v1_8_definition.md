# Phase G337: Requirement Gap Closure (QF-097)

## Goal
- Close requirement gap `QF-097` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:182`.

## Requirements
- Requirement IDs: QF-097
- Owner Track: impl_fetchdata
- Clause[QF-097]: QA‑Fetch FetchData Implementation Spec (v1) / 8. Definition of Done（主路闭环验收）

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
1. Confirm dependency gate:
   - Validate `G336` is `implemented` and `QF-096` is `implemented` in `docs/12_workflows/skeleton_ssot_v1.yaml`.
2. Read `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md` section 8 and distill the main-path closed-loop DoD acceptance checks into runtime/test updates.
3. Add explicit QF-097 clause anchors in `src/quant_eam/qa_fetch/runtime.py`:
   - add `FETCHDATA_IMPL_CLOSED_LOOP_DOD_REQUIREMENT_ID` / source document / clause constants.
4. Add/update runtime anchor test in `tests/test_qa_fetch_runtime.py` for `QF-097`.
5. Write back SSOT in `docs/12_workflows/skeleton_ssot_v1.yaml`:
   - set `G337` as `implemented`;
   - set `QF-097` as `implemented`;
   - map `QF-097` to `mapped_goal_ids: [G337]`.

## Acceptance Record
- `python3 scripts/check_docs_tree.py`
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py`
- `rg -n "G337|QF-097" docs/12_workflows/skeleton_ssot_v1.yaml`
