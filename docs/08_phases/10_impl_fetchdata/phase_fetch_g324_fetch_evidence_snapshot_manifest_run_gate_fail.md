# Phase G324: Requirement Gap Closure (QF-082)

## Goal
- Close requirement gap `QF-082` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:151`.

## Requirements
- Requirement IDs: QF-082
- Owner Track: impl_fetchdata
- Clause[QF-082]: 任何缺失 fetch evidence / snapshot manifest 的 run 必须 gate fail（不可默默跳过）。

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
TBD by controller at execution time.

## Execution Record
- Verified dependency before implementation:
  - `G322` is `status_now: implemented` in `docs/12_workflows/skeleton_ssot_v1.yaml`.
- Hardened runtime gate behavior in `src/quant_eam/qa_fetch/runtime.py`:
  - Enforced run-level hard gate for `run_id` flows after evidence write:
    - Missing fetch evidence file(s) => fail.
    - Missing snapshot manifest => fail.
    - No silent skip allowed for run-scoped execution.
  - Added run-scoped failure context (`run_id`) in gate verdict and exception message
    to make missing artifact diagnosis explicit.
  - Wired gate enforcement into:
    - `execute_fetch_by_name(...)` / `execute_fetch_by_intent(...)` run-scoped path
      via `_finalize_fetch_execution_result(...)`.
    - `execute_ui_llm_query(...)` run-scoped path after dossier-path validation.
- Updated tests in `tests/test_qa_fetch_runtime.py`:
  - Added run-path negative test for missing snapshot manifest under `run_id`.
  - Added parameterized gate negative tests:
    - missing evidence only
    - missing manifest only
    - both missing
  - Updated existing `run_id` positive tests to provide a real snapshot manifest path
    so hard-gate pass path remains explicit and deterministic.
- Updated SSOT mapping in `docs/12_workflows/skeleton_ssot_v1.yaml`:
  - Added implemented goal block `G324`.
  - Marked `QF-082` as implemented and mapped to `G324`.
  - Moved `QF-082` capability cluster linkage to `CL_FETCH_324`.

## Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py` passed.
- `rg -n "G324|QF-082" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
