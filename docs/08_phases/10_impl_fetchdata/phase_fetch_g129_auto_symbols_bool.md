# Phase G129: Requirement Gap Closure (QF-046)

## Goal
- Close requirement gap `QF-046` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:86`.

## Requirements
- Requirement ID: QF-046
- Owner Track: impl_fetchdata
- Clause: auto_symbols（bool，可选）

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
- Add an explicit runtime clause anchor for QF-046 so `auto_symbols` bool semantics are machine-checkable.
- Enforce strict runtime typing for `auto_symbols` when provided (must be `bool`; otherwise raise a deterministic validation error).
- Keep planner behavior unchanged for valid bool inputs (`True` enables planner path, `False`/`None` keep regular path).
- Add runtime tests that lock both the anchor and strict type validation.

### Execution Record
- Updated `src/quant_eam/qa_fetch/runtime.py`:
  - Added `INTENT_OPTIONAL_AUTO_SYMBOLS_BOOL` as the QF-046 clause anchor.
  - Hardened `_coerce_optional_bool(...)` to enforce bool-or-None semantics and raise on invalid types.
  - Applied auto-symbols type validation in both dict intent coercion and `FetchIntent` object coercion paths.
- Updated `tests/test_qa_fetch_runtime.py`:
  - Added `test_runtime_intent_auto_symbols_anchor_matches_qf_046_clause`.
  - Added `test_execute_fetch_by_intent_rejects_invalid_auto_symbols_type`.
- Updated `docs/12_workflows/skeleton_ssot_v1.yaml`:
  - `G129` set to `implemented`.
  - `QF-046` set to `implemented`.
  - `CL_FETCH_129` roll-up set to `implemented`.

### Acceptance Record
- `python3 scripts/check_docs_tree.py`
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py`
- `rg -n "G129|QF-046" docs/12_workflows/skeleton_ssot_v1.yaml`
