# Budget/Stop v1 (Workflow Governance)

This document defines how `budget_policy_v1` is used by the deterministic workflow plumbing.

## Why This Exists

Without budget/stop enforcement, iterative workflows can:

- loop forever (infinite spawn / infinite proposals)
- overfit by brute force (even without “parameter search”, repeated retries are still a risk)
- pollute audit trails

Budget/stop is a **core non-negotiable** governance requirement.

## Policy Asset

- Asset: `policies/budget_policy_v1.yaml`
- Contract/validation: `python -m quant_eam.policies.validate policies/budget_policy_v1.yaml`

## Enforced Limits (v1)

1) `max_proposals_per_job`

- Enforced when generating `improvement_proposals.json`.
- Orchestrator must not write more proposals than this limit.

2) `max_spawn_per_job`

- Enforced when spawning child jobs from a base job’s proposals.
- Spawn attempts beyond the limit must be rejected.
- Counting rule: this is counted per **base job** (parent job id), not aggregated across the entire lineage.

3) `max_total_iterations`

- Defines maximum lineage depth; root job generation is `0`.
- Spawn that would create a child job with `generation >= max_total_iterations` must be rejected.
- Counting rule: this is based on lineage from `root_job_id` (depth from root), not "number of jobs created".

## Evidence (STOPPED_BUDGET)

When a spawn/proposals action is blocked by budget rules, the workflow appends a `STOPPED_BUDGET` event to `events.jsonl`
with the stop reason and the current counters/limits for audit.

## What This Does Not Do (v1)

- No parameter search in the Phase-13 improvement workflow itself.
- No adaptive optimization.
- No “agent decides pass/fail”.

Note:

- Phase-23 introduces an explicit, budgeted `param_sweep_v1` workflow that is governed by `budget_policy_v1` and must preserve holdout minimal-output rules.
