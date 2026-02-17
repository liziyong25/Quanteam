# Whole View Autopilot Queue-Empty Protocol v1

## Purpose

Define mandatory behavior when unattended controller observes an empty executable queue.

This protocol prevents premature stop after `done_criteria` and keeps rolling development alive.

Controller reference implementation:

- `python3 scripts/whole_view_autopilot.py --mode controller`

## Trigger

Queue-empty generation is triggered only when all conditions are true:

- `whole_view_autopilot_v1.rolling_goal_policy.enabled = true`
- `whole_view_autopilot_v1.rolling_goal_policy.trigger_when_no_planned_or_partial = true`
- no goal in `goal_checklist` has status in `{planned, partial, in_progress}`
- Done criteria is **not** fully satisfied yet

Protocol switch:

- `queue_empty_generation_protocol_v1.allow_generate_after_done`:
  - `false` (default): keep done-guard, do not generate after full completion
  - `true`: allow continued rolling generation even after done criteria are currently satisfied

## Required Actions

1. Generate one `skeleton` goal and one `impl_fetchdata` goal.
2. Assign new IDs by strict increment from current max `G<n>`.
3. Generate two phase docs:
- `docs/08_phases/00_skeleton/phase_skel_g<n>_rolling_queue_empty_contract_freeze.md`
- `docs/08_phases/10_impl_fetchdata/phase_fetch_g<n>_rolling_queue_empty_runtime_smoke.md`
4. Write both goals into SSOT with:
- `status_now: planned`
- disjoint `allowed_paths`
- executable `acceptance_commands`
- `capability_cluster_id`
5. Append corresponding requirement trace rows (`AUTO-xxx`) into `requirements_trace_v1`.
6. Append one new planned cluster row into `capability_clusters_v1`.
7. Continue normal lifecycle:
- publish -> dispatch -> acceptance -> packet -> ssot_writeback

## Safety Constraints

- Redline deny by default remains active:
  - `contracts/**`
  - `policies/**`
  - Holdout visibility expansion
- No destructive git commands.
- Dirty workspace commit isolation must use path whitelist.

## Done Guard

When this protocol is enabled, controller must attempt queue-empty generation before declaring done.
By default it must not generate new goals once all done criteria are already satisfied, unless
`allow_generate_after_done=true`.

Stop is allowed only if:

- protocol disabled by SSOT
- generation failed and became unrecoverable blocked state
