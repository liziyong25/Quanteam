# Phase G303: Requirement Gap Closure (QF-054)

## Goal
- Close requirement gap `QF-054` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:103`.

## Requirements
- Requirement IDs: QF-054
- Owner Track: impl_fetchdata
- Clause[QF-054]: coverage（symbols 覆盖、缺失率）

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
1. Confirm dependency `G300` is already implemented and `FetchResultMeta` outputs are consumable.
2. Implement `QF-054` coverage metrics in `src/quant_eam/qa_fetch/runtime.py` with explicit definitions:
   - Symbol coverage scope: requested-symbol set extracted from request selectors (`symbols`, `symbol`, `code`) across top-level, `intent.extra_kwargs`, and `kwargs`.
   - Missing-rate formula: `missing_symbol_count / requested_symbol_count`.
   - Reporting granularity: request-level summary plus deterministic symbol lists (`requested/observed/covered/missing`).
3. Emit both compatibility fields (`symbol_coverage_ratio`, `symbol_missing_ratio`) and explicit rate fields (`symbol_coverage_rate`, `symbol_missing_rate`) with numerator/denominator metadata.
4. Add runtime tests for QF-054 edge cases:
   - duplicate/mixed selector extraction;
   - zero-denominator behavior (`requested_symbol_count=0`).
5. Update SSOT mapping (`docs/12_workflows/skeleton_ssot_v1.yaml`) to mark `G303` and `QF-054` implemented with cluster linkage.

## Acceptance
- `python3 scripts/check_docs_tree.py`
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py`
- `rg -n "G303|QF-054" docs/12_workflows/skeleton_ssot_v1.yaml`
