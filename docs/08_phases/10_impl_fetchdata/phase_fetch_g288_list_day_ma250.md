# Phase G288: Requirement Gap Closure (QF-035)

## Goal
- Close requirement gap `QF-035` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:67`.

## Requirements
- Requirement IDs: QF-035
- Owner Track: impl_fetchdata
- Clause[QF-035]: *_list → 选择样本 → *_day（例如 MA250 年线用例）

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

## Execution Notes
- Dependency baseline: `G286` remains `implemented` in `docs/12_workflows/skeleton_ssot_v1.yaml`.
- Dependency gate re-verified on `2026-02-15`: `G286` goal block still reports `status_now: implemented`.
- Runtime now treats `extra_kwargs.code` as an explicit selector in auto-symbol trigger checks.
- Request-symbol extraction includes `code` (for coverage/evidence consistency when day requests use code selectors).
- Planner sample method normalization is enforced before evidence emission, keeping sample-step evidence deterministic.
- Runtime acceptance rerun on `2026-02-15`: `python3 -m pytest -q tests/test_qa_fetch_runtime.py` -> `173 passed`.

## Acceptance
- Required acceptance commands are executed in this phase scope:
  - `python3 scripts/check_docs_tree.py`
  - `python3 -m pytest -q tests/test_qa_fetch_runtime.py`
  - `rg -n "G288|QF-035" docs/12_workflows/skeleton_ssot_v1.yaml`
