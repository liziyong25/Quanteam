# Phase G209: Requirement Gap Closure (QF-120)

## Goal
- Close requirement gap `QF-120` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:211`.

## Requirements
- Requirement ID: QF-120
- Owner Track: impl_fetchdata
- Clause: 适用于验证“notebook 参数集是否可拿到数据”。

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
### 1) Runtime contract closure for notebook-params data verification
- Add a deterministic runtime anchor:
  - `NOTEBOOK_PARAMS_DATA_VERIFICATION_RULE = notebook_params_probe_requires_pass_has_data`
- Enforce notebook-params probe-summary contract in `load_probe_summary(...)`:
  - when loading `probe_summary_v3_notebook_params.json`, `pass_has_data` must be present and `> 0`,
  - reject summaries that cannot prove notebook parameter set fetches data.

### 2) Regression test coverage for QF-120
- Extend `tests/test_qa_fetch_runtime.py` with:
  - a positive test that accepts notebook-params summary with `pass_has_data > 0`,
  - a negative test that rejects notebook-params summary with `pass_has_data == 0`,
  - an anchor test asserting QF-120 constant.

### 3) SSOT writeback
- Update `docs/12_workflows/skeleton_ssot_v1.yaml`:
  - goal `G209` status to `implemented`,
  - requirement `QF-120` status to `implemented`,
  - capability cluster `CL_FETCH_209` status to `implemented`,
  - linked interface-contract rows for `QF-120` status to `implemented`.

## Execution Record
- Date: 2026-02-14.
- Implemented notebook-params data verification contract in:
  - `src/quant_eam/qa_fetch/runtime.py`
- Added regression coverage in:
  - `tests/test_qa_fetch_runtime.py`
- Scope outcome:
  - Notebook-parameter probe summary now explicitly enforces non-zero `pass_has_data` for notebook-params validation semantics.

## Acceptance Record
- `python3 scripts/check_docs_tree.py`
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py`
- `rg -n "G209|QF-120" docs/12_workflows/skeleton_ssot_v1.yaml`
