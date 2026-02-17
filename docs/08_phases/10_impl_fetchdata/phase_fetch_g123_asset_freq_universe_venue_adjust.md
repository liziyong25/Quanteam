# Phase G123: Requirement Gap Closure (QF-042)

## Goal
- Close requirement gap `QF-042` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:82`.

## Requirements
- Requirement ID: QF-042
- Owner Track: impl_fetchdata
- Clause: asset, freq, (universe/venue), adjust

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
- Accept `universe` as a fetch-intent alias of `venue` so requests satisfy the
  `asset, freq, (universe/venue), adjust` contract without breaking existing callers.
- Keep resolver-facing behavior canonical on `venue`, with deterministic precedence:
  explicit `venue` overrides `universe`.
- Preserve request/evidence traceability by carrying `universe` through normalized intent payloads.

### Execution Record
- Updated `src/quant_eam/qa_fetch/runtime.py`:
  - Extended `FetchIntent` with optional `universe`.
  - Added alias normalization (`universe -> venue`) for intent coercion and resolver dispatch.
  - Updated fetch-request wrapper unwrapping to merge `universe` from top-level into `intent`.
  - Included `universe` in intent evidence payload.
- Updated `tests/test_qa_fetch_runtime.py`:
  - Added `test_execute_fetch_by_intent_accepts_universe_alias_in_nested_intent`.
  - Added `test_execute_fetch_by_intent_prefers_explicit_venue_over_universe`.
  - Added `test_execute_fetch_by_intent_merges_top_level_universe_into_intent`.
- Updated SSOT writeback in `docs/12_workflows/skeleton_ssot_v1.yaml`:
  - `G123` set to `implemented`.
  - `QF-042` set to `implemented`.
  - `CL_FETCH_123` roll-up set to `implemented`.

### Acceptance Record
- `python3 scripts/check_docs_tree.py`
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py`
- `rg -n "G123|QF-042" docs/12_workflows/skeleton_ssot_v1.yaml`
