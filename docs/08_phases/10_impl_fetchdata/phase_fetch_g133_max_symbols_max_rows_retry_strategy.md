# Phase G133: Requirement Gap Closure (QF-049)

## Goal
- Close requirement gap `QF-049` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:90`.

## Requirements
- Requirement ID: QF-049
- Owner Track: impl_fetchdata
- Clause: （可选）max_symbols/max_rows/retry_strategy

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
- Add an explicit runtime clause anchor for `QF-049` so `max_symbols/max_rows/retry_strategy` is machine-checkable.
- Extend `FetchExecutionPolicy` and policy coercion with optional fields:
  - `max_symbols` (positive integer when provided)
  - `max_rows` (positive integer when provided)
  - `retry_strategy` (object when provided; supports `max_attempts`)
- Enforce execution semantics in runtime:
  - cap symbol selectors (`symbols` / `symbol` / `code`) by `max_symbols` before callable invocation;
  - cap normalized payload rows by `max_rows` after no-lookahead filtering;
  - use `retry_strategy.max_attempts` as the retry attempt budget when `on_no_data=retry`.
- Add targeted runtime tests for anchor, coercion, validation, and execution behavior.

### Execution Record
- Updated `src/quant_eam/qa_fetch/runtime.py`:
  - Added `POLICY_OPTIONAL_EXECUTION_CONTROLS` as the QF-049 clause anchor.
  - Extended `FetchExecutionPolicy` with `max_symbols`, `max_rows`, and `retry_strategy`.
  - Enforced symbol and row limits in `execute_fetch_by_name`.
  - Added `retry_strategy.max_attempts` support for no-data retry execution.
  - Applied planner sampling cap via `max_symbols`.
- Updated `tests/test_qa_fetch_runtime.py`:
  - Added QF-049 anchor test and runtime coverage for `max_symbols`, `max_rows`, and `retry_strategy.max_attempts`.
  - Added validation tests for invalid optional policy shapes.
- Updated `docs/12_workflows/skeleton_ssot_v1.yaml`:
  - Marked `G133` as implemented.
  - Marked `QF-049` as implemented.
  - Marked `CL_FETCH_133` roll-up as implemented.

### Acceptance Record
- `python3 scripts/check_docs_tree.py`
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py`
- `rg -n "G133|QF-049" docs/12_workflows/skeleton_ssot_v1.yaml`
