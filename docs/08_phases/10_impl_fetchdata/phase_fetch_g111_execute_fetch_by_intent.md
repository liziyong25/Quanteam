# Phase G111: Requirement Gap Closure (QF-026)

## Goal
- Close requirement gap `QF-026` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:45`.

## Requirements
- Requirement ID: QF-026
- Owner Track: impl_fetchdata
- Clause: `execute_fetch_by_intent(...)`

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
- Keep implementation minimal because `execute_fetch_by_intent(...)` already exists and is exercised by runtime tests.
- Add an explicit QF-026 clause anchor in runtime so the interface contract is machine-checkable.
- Add focused regression coverage to ensure the clause anchor resolves to the actual runtime entrypoint.
- Verify SSOT references for `G111` and `QF-026` remain discoverable by acceptance grep.

### Execution Record
- Updated `src/quant_eam/qa_fetch/runtime.py`:
  - Added `RUNTIME_INTENT_ENTRYPOINT_NAME = "execute_fetch_by_intent"` as the explicit QF-026 contract anchor.
- Updated `tests/test_qa_fetch_runtime.py`:
  - Added `test_runtime_intent_entrypoint_matches_qf_026_clause` to lock the runtime anchor and entrypoint binding.
- Verified `docs/12_workflows/skeleton_ssot_v1.yaml` still resolves `G111` and `QF-026` entries under acceptance grep.

### Acceptance Record
- `python3 scripts/check_docs_tree.py`
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py`
- `rg -n "G111|QF-026" docs/12_workflows/skeleton_ssot_v1.yaml`
