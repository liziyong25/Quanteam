# Phase Skel G78: Fetch Structural Sanity Checks Contract Freeze

## 1) Goal
Freeze structural sanity check output contract for fetch runtime evidence metadata.

## 2) Requirements
- MUST define deterministic sanity summary fields for monotonicity, duplicate timestamps, and missing ratio.
- MUST keep contract additive and backward-compatible with existing fetch status semantics.
- MUST remain documentation-only.
- MUST NOT modify `contracts/**`, `policies/**`, or holdout visibility scope.

## 3) Architecture & Interfaces
- Inputs:
  - `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md` section 6.3
  - Existing runtime evidence meta (`fetch_result_meta.json`)
- Outputs:
  - frozen sanity-check metadata contract doc

## 4) Out-of-scope
- Runtime implementation changes.
- Gate policy or schema changes.
- UI changes.

## 5) DoD
- `python3 scripts/check_docs_tree.py`
- `rg -n "G78|sanity checks|monotonic|missing ratio|qa_fetch_sanity" docs/12_workflows/skeleton_ssot_v1.yaml docs/05_data_plane/qa_fetch_sanity_checks_contract_v1.md`

## 6) Implementation Plan
### 6.1 Execution Strategy
- Add a contract doc that freezes required sanity summary fields and deterministic computation rules.
- Keep definitions implementation-agnostic to support runtime-only rollout in impl track.

### 6.2 Controller Execution Record
- Published packet task card: `artifacts/subagent_control/G78/task_card.yaml`.
- Added contract freeze doc:
  - `docs/05_data_plane/qa_fetch_sanity_checks_contract_v1.md`

### 6.3 Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `rg -n "G78|sanity checks|monotonic|missing ratio|qa_fetch_sanity" docs/12_workflows/skeleton_ssot_v1.yaml docs/05_data_plane/qa_fetch_sanity_checks_contract_v1.md` passed.
- `python3 scripts/check_subagent_packet.py --phase-id G78` passed via packet finish lifecycle.
