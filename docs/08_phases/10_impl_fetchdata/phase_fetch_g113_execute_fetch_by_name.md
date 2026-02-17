# Phase G113: Requirement Gap Closure (QF-027)

## Goal
- Close requirement gap `QF-027` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:46`.

## Requirements
- Requirement ID: QF-027
- Owner Track: impl_fetchdata
- Clause: `execute_fetch_by_name(...)`

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
- Keep implementation minimal because `execute_fetch_by_name(...)` already exists and is exercised by runtime tests.
- Add an explicit QF-027 clause anchor in runtime so the interface contract is machine-checkable.
- Add focused regression coverage to ensure the clause anchor resolves to the actual runtime entrypoint.
- Verify SSOT references for `G113` and `QF-027` remain discoverable by acceptance grep.

### Execution Record
- Updated `src/quant_eam/qa_fetch/runtime.py`:
  - Added `RUNTIME_NAME_ENTRYPOINT_NAME = "execute_fetch_by_name"` as the explicit QF-027 contract anchor.
- Updated `tests/test_qa_fetch_runtime.py`:
  - Added `test_runtime_name_entrypoint_matches_qf_027_clause` to lock the runtime anchor and entrypoint binding.
- Verified `docs/12_workflows/skeleton_ssot_v1.yaml` still resolves `G113` and `QF-027` entries under acceptance grep.

### Acceptance Record
- `python3 scripts/check_docs_tree.py`
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py`
- `rg -n "G113|QF-027" docs/12_workflows/skeleton_ssot_v1.yaml`
