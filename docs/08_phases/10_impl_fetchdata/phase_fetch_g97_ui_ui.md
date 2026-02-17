# Phase G97: Requirement Gap Closure (QF-012)

## Goal
- Close requirement gap `QF-012` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:24`.

## Requirements
- Requirement ID: QF-012
- Owner Track: impl_fetchdata
- Clause: UI 的交互实现（但必须规定 UI 可审阅的证据接口与产物）。

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
- Reuse the existing UI-facing fetch runtime path (`execute_ui_llm_query`) as the QF-012 implementation anchor.
- Lock the UI-review evidence interface with deterministic runtime tests (required evidence artifact pointers + step index artifact).
- Perform SSOT writeback so requirement/goal/cluster/interface-contract status is aligned to implemented.

### Concrete Changes
- Updated `tests/test_qa_fetch_runtime.py`:
  - Strengthened `execute_ui_llm_query` coverage to assert required UI evidence artifact paths are always returned:
    - `fetch_request_path`
    - `fetch_result_meta_path`
    - `fetch_preview_path`
    - `fetch_steps_index_path`
  - Added assertions that `fetch_steps_index.json` is persisted and points to the same canonical result-meta path returned to UI callers.
- Updated `docs/12_workflows/skeleton_ssot_v1.yaml`:
  - `G97` marked implemented.
  - `QF-012` marked implemented.
  - `CL_FETCH_097` marked implemented.
  - All `interface_contracts_v1` rows with `impl_requirement_id: QF-012` marked implemented.
- Updated this phase card to replace placeholder plan text with deterministic execution evidence.

### Acceptance Record
- `python3 scripts/check_docs_tree.py`
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py`
- `rg -n "G97|QF-012" docs/12_workflows/skeleton_ssot_v1.yaml`
