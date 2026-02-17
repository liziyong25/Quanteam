# Phase G85: Requirement Gap Closure (QF-006)

## Goal
- Close requirement gap `QF-006` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:16`.

## Requirements
- Requirement ID: QF-006
- Owner Track: impl_fetchdata
- Clause: 通过统一 runtime 解析/执行 fetch；

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
- Keep `fetch_request` parsing/execution on a single runtime path by routing facade `execute_fetch_request(...)` through runtime intent parsing.
- Preserve function-mode metadata (`source_hint`, `public_function`) during runtime unwrap so function wrapper requests remain deterministic.
- Add regression coverage to lock forwarding behavior for runtime and facade wrappers.

### Execution Record
- Updated `src/quant_eam/qa_fetch/runtime.py`:
  - `FetchIntent` now carries `source_hint`/`public_function`.
  - `execute_fetch_by_intent(...)` forwards those fields when executing `function_override`.
  - fetch-request unwrap logic now preserves these fields from wrapper payloads.
- Updated `src/quant_eam/qa_fetch/facade.py`:
  - `execute_fetch_request(...)` now delegates to `execute_fetch_by_intent(...)` as the unified parse/execute path.
- Updated tests:
  - `tests/test_qa_fetch_runtime.py`
  - `tests/test_qa_fetch_dataaccess_facade_phase77.py`

### Acceptance Record
- `python3 scripts/check_docs_tree.py`
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py`
- `rg -n "G85|QF-006" docs/12_workflows/skeleton_ssot_v1.yaml`
