# Phase G195: Requirement Gap Closure (QF-102)

## Goal
- Close requirement gap `QF-102` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:177`.

## Requirements
- Requirement ID: QF-102
- Owner Track: impl_fetchdata
- Clause: reject → 回退并允许修改 fetch_request（或重跑）

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
### 1) Runtime clause anchor
- Add explicit QF-102 anchors in `src/quant_eam/qa_fetch/runtime.py`:
  - `FETCH_REVIEW_CHECKPOINT_REJECT_ACTION`
  - `FETCH_REVIEW_CHECKPOINT_REJECT_TRANSITION`
- Bind them to deterministic reject semantics:
  - action: `reject`
  - transition: `rollback_and_allow_fetch_request_edit_or_rerun`

### 2) Regression coverage
- Extend `tests/test_qa_fetch_runtime.py` with
  `test_runtime_fetch_review_checkpoint_reject_transition_anchor_matches_qf_102_clause`.
- Assert runtime anchors match the QF-102 reject-to-rollback-and-rerun/edit contract.

### 3) SSOT writeback
- Mark `G195` as `implemented`.
- Mark `QF-102` as `implemented`.
- Mark `CL_FETCH_195` as `implemented`.
- Mark linked interface contracts with `impl_requirement_id: QF-102` as `implemented`.

## Execution Record
- Date: 2026-02-14.
- Scope outcome:
  - Runtime now exposes explicit QF-102 reject checkpoint anchors.
  - Runtime tests lock reject action and rollback/edit-or-rerun transition semantics.
  - SSOT requirement-goal-cluster/interface linkage is written back to implemented state.

## Acceptance Record
- `python3 scripts/check_docs_tree.py` passed (`docs tree: OK`).
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py` passed (`108 passed, 37 warnings`).
- `rg -n "G195|QF-102" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
