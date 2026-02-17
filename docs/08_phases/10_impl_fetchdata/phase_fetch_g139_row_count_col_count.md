# Phase G139: Requirement Gap Closure (QF-055)

## Goal
- Close requirement gap `QF-055` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:100`.

## Requirements
- Requirement ID: QF-055
- Owner Track: impl_fetchdata
- Clause: row_count/col_count

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
1. Runtime meta contract hardening:
   - Updated `src/quant_eam/qa_fetch/runtime.py` to anchor QF-055 with
     `FETCH_RESULT_META_ROW_COL_COUNT_FIELDS = ("row_count", "col_count")`.
   - Updated `_build_fetch_meta_doc(...)` to write both `row_count` and
     `col_count` deterministically from the runtime result.
2. Regression coverage:
   - Added `tests/test_qa_fetch_runtime.py::test_runtime_fetch_result_meta_row_col_count_fields_anchor_matches_qf_055_clause`.
   - Extended `tests/test_qa_fetch_runtime.py::test_write_fetch_evidence_emits_steps_index`
     to assert persisted `fetch_result_meta.json` includes `row_count` alongside
     `col_count`.
3. SSOT writeback:
   - Updated `docs/12_workflows/skeleton_ssot_v1.yaml` to mark `G139`, `QF-055`,
     `CL_FETCH_139`, and linked interface contracts as implemented.

## Acceptance Record
- `python3 scripts/check_docs_tree.py` passed (`docs tree: OK`).
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py` passed (`69 passed`).
- `rg -n "G139|QF-055" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
