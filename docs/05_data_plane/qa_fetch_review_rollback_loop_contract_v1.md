# QA Fetch Review Rollback Loop Contract v1

## Purpose

Freeze deterministic interaction semantics for fetch review failure, rollback, rerun, and re-review.

## Flow Contract

1. Review failure:
   - Reviewer rejects current waiting step via API/UI reject action.
2. Rollback:
   - System appends rejection evidence and returns to fallback checkpoint.
3. Rerun:
   - Reviewer triggers rerun for target agent while job remains audit-traceable.
4. Re-review:
   - UI job detail remains able to render fetch evidence viewer from dossier artifacts after rerun/re-approval cycle.

## Evidence Requirements

- Rejection evidence:
  - `outputs/rejections/reject_log.jsonl` (append-only)
  - `outputs/rejections/reject_state.json` (derived latest state)
- Rerun evidence:
  - `outputs/reruns/rerun_log.jsonl` (append-only)
  - rerun agent outputs under `outputs/agents/<agent>/reruns/<rerun_id>/`
- Fetch review evidence:
  - dossier `fetch/fetch_steps_index.json` and per-step artifacts remain readable in UI viewer.

## Determinism & Safety

- Reject/rerun operations must be append-only and must not mutate prior dossier fetch evidence.
- Viewer semantics stay read-only and evidence-driven.
- Contract is interaction/evidence-level; no policy or contract schema mutation.
