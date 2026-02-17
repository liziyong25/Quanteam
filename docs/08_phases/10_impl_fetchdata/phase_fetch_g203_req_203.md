# Phase G203: Requirement Gap Closure (QF-114)

## Goal
- Close requirement gap `QF-114` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:199`.

## Requirements
- Requirement ID: QF-114
- Owner Track: impl_fetchdata
- Clause: 集成测试覆盖：审阅失败→回退→重跑→再审阅。

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
### 1) Runtime integration coverage for review rollback loop
- Add deterministic integration coverage in `tests/test_qa_fetch_runtime.py`:
  - initial reviewable fetch evidence write,
  - reject/rollback transition assertion,
  - rerun with edited fetch request,
  - re-review approval transition assertion,
  - append-only attempt-history retention and evidence readability assertions.

### 2) Runtime behavior policy
- Keep `src/quant_eam/qa_fetch/runtime.py` behavior unchanged.
- Validate QF-114 closure through integration-style runtime evidence assertions rather than adding new runtime mutation paths.

### 3) SSOT handling
- Verify `G203` and `QF-114` linkage is present in `docs/12_workflows/skeleton_ssot_v1.yaml`.

## Execution Record
- Date: 2026-02-14.
- Added test:
  - `test_fetch_review_failure_rollback_rerun_rereview_loop_preserves_evidence_readability`
- Scope outcome:
  - Coverage now proves review failure -> rollback -> rerun -> re-review loop semantics at qa_fetch runtime evidence layer.
  - Coverage proves prior-attempt evidence immutability and latest-attempt viewer-readability after rerun.

## Acceptance Record
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py` passed (`112 passed`).
- `python3 scripts/check_docs_tree.py` passed.
- `rg -n "G203|QF-114" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
