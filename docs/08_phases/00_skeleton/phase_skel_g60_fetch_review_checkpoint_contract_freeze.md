# Phase Skeleton G60: QA Fetch Review Checkpoint Contract Freeze

## 1) Goal
Freeze the review-checkpoint contract for fetch intent planning and evidence visibility, including intent-priority and list-to-day planning expectations.

## 2) Requirements
- MUST define review checkpoint semantics for fetch planning outputs before execution-side expansion.
- MUST preserve intent-priority over provider-function hardcoding.
- MUST capture list-to-day planning expectation when symbols are absent and auto-symbol expansion is enabled.
- SHOULD keep review contract compatible with read-only UI evidence inspection.

## 3) Architecture & Interfaces
- Inputs:
  - `Quant‑EAM Whole View Framework.md（v0.5‑draft）.md`
  - `QA_Fetch_Integration_for_GPTPro.md`
  - `docs/05_data_plane/qa_fetch_registry_v1.json`
- Outputs:
  - `docs/08_phases/00_skeleton/phase_skel_g60_fetch_review_checkpoint_contract_freeze.md`
  - SSOT goal entry for G60 with checkpoint and intent constraints
- Dependencies:
  - `G30` (implemented) QA fetch read-only review baseline
- Immutable constraints:
  - Review checkpoint is evidence-only; no gate arbitration delegation to agents.

## 4) Out-of-scope
- Orchestrator state-machine code changes.
- UI API or template implementation.
- Provider function-level optimization.

## 5) DoD
- Executable commands:
  - `python3 scripts/check_docs_tree.py`
  - `rg -n "G60|phase_skel_g60|list->day|intent" docs/12_workflows/skeleton_ssot_v1.yaml`
- Expected artifacts:
  - `docs/08_phases/00_skeleton/phase_skel_g60_fetch_review_checkpoint_contract_freeze.md`
  - `docs/12_workflows/skeleton_ssot_v1.yaml`

## 6) Implementation Plan
TBD by controller at execution time (implementation details decided during execution, not in spec).
