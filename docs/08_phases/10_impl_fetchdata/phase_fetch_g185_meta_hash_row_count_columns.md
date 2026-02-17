# Phase G185: Requirement Gap Closure (QF-093)

## Goal
- Close requirement gap `QF-093` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:162`.

## Requirements
- Requirement ID: QF-093
- Owner Track: impl_fetchdata
- Clause: 固定请求 → 产出 meta/hash/row_count/columns

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
### 1) Runtime evidence verification for fixed request
- Reuse existing runtime evidence path where fixed fetch request emits:
  - `fetch_result_meta.json`
  - `request_hash`
  - `row_count`
  - `columns`
- Keep execution behavior unchanged; scope is requirement writeback plus deterministic regression assertion.

### 2) Regression coverage hardening
- Extend `tests/test_qa_fetch_runtime.py` in UI-LLM query evidence flow to assert:
  - fixed request hash equals canonical request hash
  - summary/meta include `row_count` and `columns`
  - persisted meta and summary values stay aligned

### 3) SSOT writeback
- Mark implemented status for:
  - Goal `G185`
  - Requirement `QF-093`
  - Capability cluster `CL_FETCH_185`
  - Linked interface contracts with `impl_requirement_id: QF-093`

## Execution Record
- Date: 2026-02-14.
- Scope outcome:
  - Fixed-request evidence assertions now explicitly verify `meta/hash/row_count/columns`.
  - SSOT records QF-093 as implemented and upgrades linked interface/cluster statuses.

## Acceptance Record
- `python3 scripts/check_docs_tree.py`
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py`
- `rg -n "G185|QF-093" docs/12_workflows/skeleton_ssot_v1.yaml`
