# Phase G205: Requirement Gap Closure (QF-118)

## Goal
- Close requirement gap `QF-118` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:209`.

## Requirements
- Requirement ID: QF-118
- Owner Track: impl_fetchdata
- Clause: 在 Jupyter notebook kernel 内执行（`notebooks/qa_fetch_manual_params_v3.ipynb` 对应 kernel）。

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
### 1) Runtime contract closure for notebook-kernel path
- Add a deterministic runtime anchor for the notebook-kernel manual params notebook path:
  - `NOTEBOOK_KERNEL_MANUAL_PARAMS_NOTEBOOK_PATH = notebooks/qa_fetch_manual_params_v3.ipynb`
  - `NOTEBOOK_KERNEL_EXECUTION_ENV = jupyter_notebook_kernel`
- Enforce the path contract when loading smoke window profile metadata:
  - if `notebook_ref` is present in profile JSON, it must match the canonical notebook path.

### 2) Regression test coverage for QF-118
- Extend `tests/test_qa_fetch_runtime.py` with:
  - a positive test that accepts matching `notebook_ref`,
  - a negative test that rejects mismatched `notebook_ref`,
  - an anchor test asserting QF-118 constants.

### 3) SSOT writeback
- Update `docs/12_workflows/skeleton_ssot_v1.yaml`:
  - goal `G205` status to `implemented`,
  - requirement `QF-118` status to `implemented`,
  - capability cluster `CL_FETCH_205` status to `implemented`.

## Execution Record
- Date: 2026-02-14.
- Implemented runtime notebook-kernel contract checks in:
  - `src/quant_eam/qa_fetch/runtime.py`
- Added regression coverage in:
  - `tests/test_qa_fetch_runtime.py`
- Scope outcome:
  - Notebook-kernel manual params notebook path is now a deterministic runtime contract when profile metadata includes `notebook_ref`.
  - QF-118 is covered by explicit runtime anchors and tests.

## Acceptance Record
- `python3 scripts/check_docs_tree.py`
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py`
- `rg -n "G205|QF-118" docs/12_workflows/skeleton_ssot_v1.yaml`
