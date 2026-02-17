# Phase G87: Requirement Gap Closure (PRIO-UI-LLM-002)

## Goal
- Close requirement gap `PRIO-UI-LLM-002` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:182`.

## Requirements
- Requirement ID: PRIO-UI-LLM-002
- Owner Track: impl_fetchdata
- Clause: P0 objective: UI LLM query path must execute end-to-end through qa_fetch runtime and return query result plus fetch evidence summary.

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
### Execution Strategy
- Add a dedicated UI-LLM query runtime entrypoint that always executes through `qa_fetch.runtime.execute_fetch_by_intent(...)`.
- Return a deterministic payload containing:
  - `query_result` (runtime execution output projection)
  - `fetch_evidence_summary` (same metadata model as `fetch_result_meta.json`)
- Support optional evidence writeout so UI callers can get immutable evidence pointers in the same call.

### Concrete Changes
- Updated `src/quant_eam/qa_fetch/runtime.py`:
  - Added `execute_ui_llm_query(...)` and alias `execute_ui_llm_query_path(...)`.
  - Added envelope parsing helper for `fetch_request` extraction.
  - Added query-result document builder and response envelope (`query_result` + `fetch_evidence_summary` + optional evidence pointer/paths).
- Updated `src/quant_eam/qa_fetch/facade.py`:
  - Added facade wrappers for `execute_ui_llm_query(...)` and `execute_ui_llm_query_path(...)`.
- Updated `src/quant_eam/qa_fetch/__init__.py`:
  - Exported new UI-LLM query runtime entrypoints.
- Updated tests:
  - `tests/test_qa_fetch_runtime.py` adds coverage for:
    - end-to-end UI query runtime execution path
    - direct payload compatibility
    - validation for invalid query envelope inputs
  - `tests/test_qa_fetch_exports.py` asserts package-level exports include new entrypoints.

## Execution Record
- Date: 2026-02-13.
- Requirement clause implemented by runtime path execution:
  - UI query envelope is parsed into fetch request.
  - Fetch runs via unified runtime execution path.
  - Response returns query result and fetch evidence summary.
  - Optional evidence writeback returns immutable pointer (`fetch_result_meta_path`).

## Acceptance Record
- `python3 scripts/check_docs_tree.py`
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py`
- `rg -n "G87|PRIO-UI-LLM-002" docs/12_workflows/skeleton_ssot_v1.yaml`
