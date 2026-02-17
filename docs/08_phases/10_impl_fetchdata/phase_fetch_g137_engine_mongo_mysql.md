# Phase G137: Requirement Gap Closure (QF-054)

## Goal
- Close requirement gap `QF-054` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:99`.

## Requirements
- Requirement ID: QF-054
- Owner Track: impl_fetchdata
- Clause: engine（mongo/mysql）

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
   - Updated `src/quant_eam/qa_fetch/runtime.py` to anchor QF-054 with
     `FETCH_RESULT_META_ENGINE_OPTIONS = ("mongo", "mysql")`.
   - Added `_resolve_result_engine(...)` and wired it into
     `_build_fetch_meta_doc(...)` so `fetch_result_meta.engine` falls back to
     `source_internal/provider_internal` when runtime result `engine` is unset.
2. Regression coverage:
   - Added `tests/test_qa_fetch_runtime.py::test_runtime_fetch_result_meta_engine_options_anchor_matches_qf_054_clause`.
   - Added `tests/test_qa_fetch_runtime.py::test_write_fetch_evidence_engine_falls_back_to_source_internal`
     to lock deterministic `engine` writeback in evidence meta docs.
3. SSOT writeback:
   - Updated `docs/12_workflows/skeleton_ssot_v1.yaml` to mark `G137`, `QF-054`,
     `CL_FETCH_137`, and linked interface contracts as implemented.

## Acceptance Record
- `python3 scripts/check_docs_tree.py` passed (`docs tree: OK`).
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py` passed (`68 passed`).
- `rg -n "G137|QF-054" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
