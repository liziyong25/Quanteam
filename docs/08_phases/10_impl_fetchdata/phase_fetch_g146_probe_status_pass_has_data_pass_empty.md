# Phase G146: Requirement Gap Closure (QF-059)

## Goal
- Close requirement gap `QF-059` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:104`.

## Requirements
- Requirement ID: QF-059
- Owner Track: impl_fetchdata
- Clause: probe_status（可选：pass_has_data/pass_empty）

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
   - Add a QF-059 clause anchor in `src/quant_eam/qa_fetch/runtime.py` for allowed
     optional `probe_status` values: `pass_has_data` and `pass_empty`.
   - Update fetch meta assembly to emit `probe_status` only when the runtime status
     is in that anchor set; omit it for non-pass statuses.
2. Regression coverage:
   - Add runtime anchor test for QF-059 in `tests/test_qa_fetch_runtime.py`.
   - Add evidence tests to lock optional behavior:
     - `probe_status` persists for `pass_empty`.
     - `probe_status` is absent for `error_runtime` and `blocked_source_missing`.
3. SSOT writeback:
   - Mark `G146`, `QF-059`, `CL_FETCH_146`, and linked interface contracts as
     implemented in `docs/12_workflows/skeleton_ssot_v1.yaml`.

## Acceptance Record
- `python3 scripts/check_docs_tree.py` passed (`docs tree: OK`).
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py` passed (`74 passed`).
- `rg -n "G146|QF-059" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
