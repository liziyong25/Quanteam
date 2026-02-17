# Phase G91: Requirement Gap Closure (QF-008)

## Goal
- Close requirement gap `QF-008` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:18`.

## Requirements
- Requirement ID: QF-008
- Owner Track: impl_fetchdata
- Clause: 为 DataCatalog/time‑travel 与 gates 提供可审计输入基础；

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
- Keep existing fetch runtime behavior unchanged (`status`, `reason`, payload semantics) and add only deterministic, additive evidence metadata.
- Reuse already emitted `availability_summary` and `sanity_checks` as the source of truth, then derive a single gate-facing summary for:
  - time-travel / no-lookahead evidence inputs (`available_at<=as_of`);
  - snapshot-integrity evidence inputs (timestamp monotonicity/duplicates/missing-column signals).
- Lock these fields with runtime tests so gate-facing metadata remains reproducible.

### Concrete Changes
- Added contract note:
  - `docs/05_data_plane/qa_fetch_gate_input_summary_contract_v1.md`
- Updated runtime evidence meta builder:
  - `src/quant_eam/qa_fetch/runtime.py`
  - `fetch_result_meta.json` now includes additive `gate_input_summary` with:
    - `no_lookahead`
    - `data_snapshot_integrity`
- Updated runtime regression assertions:
  - `tests/test_qa_fetch_runtime.py`
  - Added checks for populated and fallback `gate_input_summary` values.

### Acceptance Record
- `python3 scripts/check_docs_tree.py`
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py`
- `rg -n "G91|QF-008" docs/12_workflows/skeleton_ssot_v1.yaml`
