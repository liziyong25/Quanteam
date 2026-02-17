# Phase G101: Requirement Gap Closure (QF-017)

## Goal
- Close requirement gap `QF-017` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:33`.

## Requirements
- Requirement ID: QF-017
- Owner Track: impl_fetchdata
- Clause: 引擎拆分：`engine=mongo|mysql`（分布：mongo 48、mysql 23）

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
- Runtime enforcement:
  - `src/quant_eam/qa_fetch/runtime.py` validates function-registry rows carry consistent `engine` and internal source metadata.
  - Baseline payloads with `function_count=71` now enforce split `mongo=48` and `mysql=23` during registry load.
- Test coverage:
  - `tests/test_qa_fetch_runtime.py` adds contract tests for split mismatch rejection, exact split acceptance, and row-level engine/source mismatch rejection.
- SSOT writeback:
  - `docs/12_workflows/skeleton_ssot_v1.yaml` marks `QF-017` and `G101` as implemented.
