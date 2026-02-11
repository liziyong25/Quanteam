# Phase 13 — Budget/Stop v1 + ImprovementAgent v1 + Proposal Spawn

## Goal

Introduce deterministic budgets/stops and a mock deterministic ImprovementAgent that can propose next-round Blueprint candidates
from structured evidence (GateResults + ReportSummary), and allow user-selected spawning of a new job that returns to the Blueprint
review checkpoint.

## Scope

- Add `budget_policy_v1` (YAML, frozen governance input).
- Add `improvement_proposals_v1` contract for structured proposals.
- Add `improvement_agent_v1` (provider=`mock`, offline deterministic).
- Orchestrator generates proposals after report completion and stops at `WAITING_APPROVAL(step=improvements)`.
- API/UI can fetch proposals and spawn child jobs (append-only `SPAWNED` event).

## Deliverables

- `policies/budget_policy_v1.yaml`
- `contracts/improvement_proposals_schema_v1.json`
- `python -m quant_eam.contracts.validate` dispatch supports `improvement_proposals_v1`
- Jobs API:
  - `GET /jobs/{job_id}/proposals`
  - `POST /jobs/{job_id}/spawn?proposal_id=...`
- UI: proposals list + Spawn button on `/ui/jobs/{job_id}`

## Acceptance

- Offline tests (tmp_path) cover:
  - proposals generation stops at improvements checkpoint
  - spawn enforces budgets and returns to blueprint review checkpoint

## Execution Log

- Start Date: 2026-02-10 (Asia/Taipei)
- End Date: 2026-02-10 (Asia/Taipei)
- Commit: unknown (not recorded in this workspace log)

