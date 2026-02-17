# Phase Skel G80: Fetch AsOf Availability Summary Contract Freeze

## 1) Goal
Freeze fetch evidence metadata contract for `as_of` and preview-level `available_at` availability summary.

## 2) Requirements
- MUST define additive metadata fields for as_of and available_at summary.
- MUST keep semantics aligned with policy rule `available_at<=as_of`.
- MUST remain documentation-only.
- MUST NOT modify `contracts/**`, `policies/**`, or holdout visibility scope.

## 3) Architecture & Interfaces
- Inputs:
  - `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md` section 6.1
  - `Quant‑EAM Whole View Framework.md（v0.5‑draft）.md` time-travel constraints
- Outputs:
  - frozen availability summary contract document

## 4) Out-of-scope
- Runtime implementation changes.
- Gate/policy updates.
- UI changes.

## 5) DoD
- `python3 scripts/check_docs_tree.py`
- `rg -n "G80|as_of|available_at|availability summary|available_at<=as_of" docs/12_workflows/skeleton_ssot_v1.yaml docs/05_data_plane/qa_fetch_asof_availability_summary_contract_v1.md`

## 6) Implementation Plan
### 6.1 Execution Strategy
- Add a contract document that freezes required fields and deterministic behavior for as_of/available_at summary.
- Keep format implementation-agnostic but machine-readable.

### 6.2 Controller Execution Record
- Published packet task card: `artifacts/subagent_control/G80/task_card.yaml`.
- Added contract document:
  - `docs/05_data_plane/qa_fetch_asof_availability_summary_contract_v1.md`

### 6.3 Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `rg -n "G80|as_of|available_at|availability summary|available_at<=as_of" docs/12_workflows/skeleton_ssot_v1.yaml docs/05_data_plane/qa_fetch_asof_availability_summary_contract_v1.md` passed.
- `python3 scripts/check_subagent_packet.py --phase-id G80` passed via packet finish lifecycle.
