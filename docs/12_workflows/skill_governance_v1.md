# Skill Governance v1

## Purpose

Define mandatory skill declaration, enforcement mode, and reasoning-tier policy for
`whole_view_autopilot.py` controller dispatch.

## SSOT Contract

Controller reads/writes these top-level SSOT keys in `docs/12_workflows/skeleton_ssot_v1.yaml`:

- `skill_registry_v1`
- `skill_binding_policy_v1`
- `skill_enforcement_v1`
- `difficulty_scoring_v1`
- `reasoning_tiers_v1`
- `planning_policy_v2.architect_preplan_v1`

## Goal-level Fields

Each `goal_checklist[]` row must include:

- `required_skills`
- `difficulty_score`
- `reasoning_tier`

## Requirement-to-Goal Bundling Standard

Controller must avoid one-line-per-phase splitting by default. It should bundle unmet
requirements into one goal when `planning_policy_v2.goal_bundle_policy` allows and the
requirements satisfy the configured constraints (same track/source/parent, line window).
For stricter impl track behavior, use `goal_bundle_policy.track_overrides.impl_fetchdata`
and/or `impl_workbench` with tighter bounds (e.g., 2-4 req/phase target via `max=4`,
`minimum_bundle_size=3`, and `require_exact_parent_signature=true`).

## Architect Pre-Plan Stage

Before publishing new goals, controller must run `architect_preplan_v1`:

- Read configured requirement source documents.
- Produce `requirement_priority` and `goal_priority`.
- Produce `bundle_hints` and `parallel_hints`.
- Enforce skeleton-first ordering for interface dependencies.

`skill_binding_policy_v1.controller_preplan_skills` defines required skills for this stage.

## Goal TODO Planner

`planning_policy_v2.goal_todo_planner_v1` controls per-goal todo generation.
Each generated goal should include:

- `todo_checklist`
- `risk_notes`
- `parallel_hints`
- `todo_planner` metadata (mode/source/fallback reason)

## Enforcement

- `warn`: skill-check failures are logged as warnings, packet may still pass.
- `enforce`: missing/invalid skill usage evidence blocks packet acceptance.

## Reasoning Tier Mapping

- `0-39`: `medium`
- `40-69`: `high`
- `70-100`: `super_high`

Each tier maps to codex runtime knobs:

- `model`
- `timeout_sec`
- `retry`

## Packet Requirements

Task card / executor / validator reports must expose skill and reasoning evidence so
`check_subagent_packet.py` can validate `skills_*` and `reasoning_tier_applied` checks.
