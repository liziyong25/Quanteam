# Phase G340: Requirement Gap Closure (QF-106)

## Goal
- Close requirement gap `QF-106` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:202`.

## Requirements
- Requirement IDs: QF-106
- Owner Track: impl_fetchdata
- Clause[QF-106]: sanity checks + Golden Queries + time‑travel + gates 均可回归；

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.
- Bundling criterion: same owner track + same source document + same parent requirement + near-adjacent source lines.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
1. Implement regression coverage for the QF-106 umbrella in runtime + tests:
   - Sanity checks (`_build_preview_sanity_checks`, `_build_gate_input_summary`, and evidence meta wiring).
   - Golden query fixed-set execution + drift report path logic.
   - Time-travel availability summary and guard behavior (`available_at <= as_of`) for both success and fallback.
   - Gate summary/reporting for no_lookahead and data_snapshot_integrity, plus manifest gate fail path.
2. Run runtime suite assertions with deterministic fixtures under `tests/test_qa_fetch_runtime.py`.
3. Update `docs/12_workflows/skeleton_ssot_v1.yaml` to map G340 to `QF-106` and mark `QF-106` implemented.
4. Execute acceptance commands in order:
   - `python3 scripts/check_docs_tree.py`
   - `python3 -m pytest -q tests/test_qa_fetch_runtime.py`
   - `rg -n "G340|QF-106" docs/12_workflows/skeleton_ssot_v1.yaml`
