# Phase G181: Requirement Gap Closure (QF-090)

## Goal
- Close requirement gap `QF-090` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:155`.

## Requirements
- Requirement ID: QF-090
- Owner Track: impl_fetchdata
- Clause: 时间索引单调递增、无重复（或明确记录允许规则）

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
### 1) Runtime requirement execution
- Add explicit QF-090 runtime anchors in `src/quant_eam/qa_fetch/runtime.py`:
  - `SANITY_TIMESTAMP_ORDER_RULE`
  - `SANITY_TIMESTAMP_DUPLICATE_POLICY`
- Extend `sanity_checks` emission to always include:
  - `timestamp_order_rule`
  - `timestamp_duplicate_policy`
  - `timestamp_rule_satisfied`
- Extend `gate_input_summary.data_snapshot_integrity` to carry the same
  rule/policy/satisfied fields so GateRunner evidence can consume deterministic
  requirement-level semantics.

### 2) Regression coverage
- Add `test_runtime_sanity_timestamp_order_rule_anchor_matches_qf_090_clause`.
- Extend existing evidence assertions in `tests/test_qa_fetch_runtime.py` to
  verify:
  - monotonic+unique preview => `timestamp_rule_satisfied=true`
  - empty preview fallback => `timestamp_rule_satisfied=true`
  - non-monotonic/duplicate preview => `timestamp_rule_satisfied=false`

### 3) Contract and SSOT writeback
- Update docs contracts:
  - `docs/05_data_plane/qa_fetch_sanity_checks_contract_v1.md`
  - `docs/05_data_plane/qa_fetch_gate_input_summary_contract_v1.md`
- Mark SSOT entities implemented in `docs/12_workflows/skeleton_ssot_v1.yaml`:
  - `G181`
  - `QF-090`
  - `CL_FETCH_181`
  - interface mappings `IFC-QF_034-QF_090` and `IFC-QF_089-QF_090`

## Execution Record
- Date: 2026-02-14.
- Scope outcome:
  - QF-090 now has explicit runtime-recorded timestamp order policy and
    deterministic pass/fail summary in fetch evidence metadata.
  - Gate input summary now carries requirement-level timestamp rule semantics.
  - SSOT writeback marks G181/QF-090 and linked interfaces as implemented.

## Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py` passed.
- `rg -n "G181|QF-090" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
