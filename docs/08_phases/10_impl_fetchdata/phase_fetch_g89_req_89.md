# Phase G89: Requirement Gap Closure (QF-007)

## Goal
- Close requirement gap `QF-007` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:17`.

## Requirements
- Requirement ID: QF-007
- Owner Track: impl_fetchdata
- Clause: 为每次取数强制落盘证据；

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
- Enforce evidence persistence in the runtime fetch entrypoints so every fetch execution path writes a fetch evidence bundle by default.
- Keep result semantics unchanged (`status`, `reason`, `row_count`, etc.) and only add deterministic writeback side effects.
- Use a stable default evidence root keyed by request hash so repeated runs are reproducible and inspectable.

### Concrete Changes
- Updated `src/quant_eam/qa_fetch/runtime.py`:
  - Added mandatory evidence writeback finalization for both:
    - `execute_fetch_by_name(...)`
    - `execute_fetch_by_intent(...)`
  - Added deterministic default runtime evidence root:
    - `artifacts/qa_fetch/runtime_fetch_evidence/<request_hash>/`
  - Added internal request payload builders so persisted `fetch_request.json` includes function/intent context and policy.
  - Kept `execute_ui_llm_query(...)` on its existing dedicated evidence path by disabling duplicate default writeback for that call site.
- Updated tests:
  - `tests/test_qa_fetch_runtime.py` now verifies:
    - direct function-mode fetch auto-writes evidence
    - intent-mode fetch auto-writes evidence

### Acceptance Record
- `python3 scripts/check_docs_tree.py`
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py`
- `rg -n "G89|QF-007" docs/12_workflows/skeleton_ssot_v1.yaml`
