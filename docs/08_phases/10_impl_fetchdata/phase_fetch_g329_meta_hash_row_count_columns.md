# Phase G329: Requirement Gap Closure (QF-087)

## Goal
- Close requirement gap `QF-087` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:162`.

## Requirements
- Requirement IDs: QF-087
- Owner Track: impl_fetchdata
- Clause[QF-087]: 固定请求 → 产出 meta/hash/row_count/columns

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
- Confirm G328 is implemented in SSOT and reuse the existing golden-query runtime interfaces
  (`build_golden_query_execution_summary`, `query_outputs`, drift-report readers).
- Extend golden-query runtime summary artifacts so each fixed request emits the QF-087
  quartet: `meta`, `request_hash`, `row_count`, `columns`.
- Keep hash deterministic via canonical request hashing (`_canonical_request_hash`)
  and normalized/sorted columns from existing output normalization.
- Add runtime tests for:
  - QF-087 clause anchors and artifact field contract.
  - Fixed-request quartet presence in summary artifacts.
  - Deterministic hash for equivalent requests with different key ordering.
  - Empty/non-empty row_count behavior in fixed-request artifacts.
- Write SSOT updates for goal `G329` and requirement trace `QF-087 -> implemented`.
- Run acceptance commands and archive command logs under `artifacts/subagent_control/G329/`.
