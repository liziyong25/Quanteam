# Phase G99: Requirement Gap Closure (QF-016)

## Goal
- Close requirement gap `QF-016` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:32`.

## Requirements
- Requirement ID: QF-016
- Owner Track: impl_fetchdata
- Clause: 对外语义：`source=fetch`

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
- Treat `source=fetch` as an external contract and enforce it at runtime serialization boundaries.
- Add deterministic runtime regression coverage to prevent outward semantic drift.
- Perform SSOT writeback so `G99` and `QF-016` linkage is explicit in the current workflow baseline.

### Concrete Changes
- Updated `src/quant_eam/qa_fetch/runtime.py`:
  - Outward result payload now always emits `source: "fetch"` in:
    - `query_result` (`_build_query_result_doc`)
    - `fetch_result_meta` (`_build_fetch_meta_doc`)
    - `fetch_error.json` (`write_fetch_evidence`)
    - fallback `fetch_preview.csv` summary row (`_write_preview_csv`)
- Updated `tests/test_qa_fetch_runtime.py`:
  - Added `test_execute_ui_llm_query_enforces_public_source_fetch_semantics` to lock the outward `source=fetch` contract in UI query result and persisted `fetch_result_meta.json`.
- Updated `docs/12_workflows/skeleton_ssot_v1.yaml`:
  - `G99` entry aligned to this requirement-gap phase card and acceptance command (`G99|QF-016`).
  - `QF-016` trace mapping linked to `G99` under `CL_FETCH_099`.
  - `CL_FETCH_099` includes `QF-016` in requirement IDs and uses requirement-aware acceptance grep.

### Acceptance Record
- `python3 scripts/check_docs_tree.py`
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py`
- `rg -n "G99|QF-016" docs/12_workflows/skeleton_ssot_v1.yaml`
