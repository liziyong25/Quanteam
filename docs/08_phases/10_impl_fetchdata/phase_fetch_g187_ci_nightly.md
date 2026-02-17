# Phase G187: Requirement Gap Closure (QF-094)

## Goal
- Close requirement gap `QF-094` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:163`.

## Requirements
- Requirement ID: QF-094
- Owner Track: impl_fetchdata
- Clause: 漂移必须产出报告（报告文件位置由主控定义，但必须可被 CI 或 nightly 读取）

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
### 1) Runtime drift report emitter
- Add deterministic runtime helpers to compare two golden summary payloads and produce a drift report.
- Keep report path controller-defined (`report_out_path`) and write report JSON in-place for CI/nightly readers.

### 2) Regression coverage
- Extend `tests/test_qa_fetch_runtime.py` with:
  - clause anchor assertions for QF-094 runtime constants;
  - drift detection coverage (added/removed/changed golden query ids);
  - controller-defined output path write test for CI/nightly report consumption.

### 3) Docs + SSOT writeback
- Update `docs/05_data_plane/qa_fetch_golden_queries_v1.md` with QF-094 drift report field contract.
- Mark `G187` / `QF-094` and linked capability/interface nodes as implemented in SSOT.

## Execution Record
- Date: 2026-02-14.
- Scope outcome:
  - Runtime now provides `build_golden_query_drift_report(...)` and `write_golden_query_drift_report(...)`.
  - Drift report output path is explicitly caller/controller-defined and persisted as JSON for CI/nightly.
  - Runtime tests now enforce QF-094 anchor + drift report generation behavior.

## Acceptance Record
- `python3 scripts/check_docs_tree.py`
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py`
- `rg -n "G187|QF-094" docs/12_workflows/skeleton_ssot_v1.yaml`
