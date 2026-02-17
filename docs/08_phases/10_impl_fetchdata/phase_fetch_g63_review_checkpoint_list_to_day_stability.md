# Phase Fetch G63: Review Checkpoint List-to-Day Stability

## 1) Goal
Implement stable review-checkpoint behavior for fetch intent planning, including list-to-day expansion evidence and deterministic checkpoint outputs.

## 2) Requirements
- MUST support intent-first planning output suitable for review checkpoints.
- MUST preserve list-to-day planning semantics when symbol list expansion is required.
- MUST emit deterministic checkpoint evidence consumable by read-only review pages.
- SHOULD keep compatibility with existing registry/probe payload conventions.

## 3) Architecture & Interfaces
- Inputs:
  - Fetch planning intent and optional auto-symbol flags
  - `src/quant_eam/qa_fetch/runtime.py`
  - `src/quant_eam/qa_fetch/probe.py`
- Outputs:
  - Stable review-checkpoint evidence artifacts and related tests
  - `docs/08_phases/10_impl_fetchdata/phase_fetch_g63_review_checkpoint_list_to_day_stability.md`
- Dependencies:
  - `G60` (planned skeleton review checkpoint contract freeze)
- Immutable constraints:
  - Deterministic replay compatibility, append-only evidence, GateRunner arbitration boundary unchanged.

## 4) Out-of-scope
- Contract schema version changes.
- Gate suite policy changes.
- UI business-flow redesign.

## 5) DoD
- Executable commands:
  - `python3 scripts/check_docs_tree.py`
  - `docker compose run --rm api pytest -q tests/test_qa_fetch_probe.py tests/test_ui_mvp.py`
- Expected artifacts:
  - `docs/08_phases/10_impl_fetchdata/phase_fetch_g63_review_checkpoint_list_to_day_stability.md`
  - `artifacts/subagent_control/G63/task_card.yaml`
  - `artifacts/subagent_control/G63/workspace_before.json`

## 6) Implementation Plan
### 6.1 Execution Strategy
- Validate existing runtime/probe behavior against G60 frozen review-checkpoint semantics.
- Keep scope minimal and deterministic; avoid non-essential fetch runtime rewrites.

### 6.2 Controller Execution Record
- Re-ran acceptance set covering probe + UI MVP interactions.
- Confirmed list-to-day review-checkpoint behavior remains stable and replay-compatible in current implementation baseline.
- Goal closed as stability hardening evidence with no out-of-scope route/contract/policy changes.

### 6.3 Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `docker compose run --rm api pytest -q tests/test_qa_fetch_probe.py tests/test_ui_mvp.py` passed.
