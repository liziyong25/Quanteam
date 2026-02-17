# Phase Fetch G83: Fetch Review Rollback Rerun Re-Review Integration Test

## 1) Goal
Add deterministic fetch-specific integration coverage for review failure -> rollback -> rerun -> re-review with UI evidence visibility.

## 2) Requirements
- MUST cover reject fallback and rerun append-only evidence in one flow.
- MUST assert fetch evidence viewer remains visible for re-review.
- MUST keep viewer read-only semantics.
- MUST NOT modify `contracts/**`, `policies/**`, or holdout visibility scope.

## 3) Architecture & Interfaces
- Inputs:
  - `docs/05_data_plane/qa_fetch_review_rollback_loop_contract_v1.md`
  - existing `/jobs/{job_id}/reject`, `/jobs/{job_id}/rerun`, `/jobs/{job_id}/approve`, `/ui/jobs/{job_id}`
- Outputs:
  - integration test coverage proving rollback-loop evidence visibility for fetch review

## 4) Out-of-scope
- Policy changes.
- Provider/runtime fetch logic changes.
- Contract schema changes.

## 5) DoD
- `python3 scripts/check_docs_tree.py`
- `docker compose run --rm api pytest -q tests/test_fetch_review_rollback_phase83.py tests/test_ui_fetch_evidence_viewer_phase73.py`

## 6) Implementation Plan
### 6.1 Execution Strategy
- Build a deterministic API/UI integration test:
  - create idea job and advance to waiting approval;
  - seed dossier fetch evidence;
  - run reject -> rerun -> approve sequence;
  - assert UI page contains fetch viewer + rejection evidence + rerun evidence.
- Keep implementation in tests only unless viewer wiring gaps are discovered.

### 6.2 Controller Execution Record
- Published packet task card: `artifacts/subagent_control/G83/task_card.yaml`.
- Added integration test:
  - `tests/test_fetch_review_rollback_phase83.py`

### 6.3 Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `docker compose run --rm api pytest -q tests/test_fetch_review_rollback_phase83.py tests/test_ui_fetch_evidence_viewer_phase73.py` passed.
- `python3 scripts/check_subagent_packet.py --phase-id G83` passed via packet finish lifecycle.
