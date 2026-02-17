---
name: ssot-goal-planner
description: Plan requirement-gap goals from `requirements_trace_v1` into `goal_checklist` with dependency-safe track routing and deterministic phase/allowed_paths/acceptance definitions.
---

# SSOT Goal Planner

## Use When

- Requirement rows exist but `goal_checklist` coverage is missing or sparse.
- Controller needs queue-empty generation from unmet requirements.
- A track requires dependency-safe `depends_on` wiring before dispatch.

## Workflow

1. Read unmet rows in `requirements_trace_v1` (`status_now != implemented`).
2. Select by owner track with dependency readiness:
- `skeleton` first for interface prerequisites.
- impl tracks only when skeleton requirement deps are implemented.
3. Bundle requirements before creating goals (do not split one line into one phase by default):
- Default bundle policy (from `planning_policy_v2.goal_bundle_policy`):
  - `enabled=true`
  - `max_requirements_per_goal=4`
  - `minimum_bundle_size=2`
  - `source_line_window=6`
- `require_same_source_document=true`
- `require_same_parent_requirement=true`
- `require_exact_parent_signature=false` (can be true in track overrides)
- `track_overrides.impl_fetchdata` / `track_overrides.impl_workbench` may enforce stricter values
  (e.g., `max_requirements_per_goal=4`, `minimum_bundle_size=3`, `require_exact_parent_signature=true`).
- Only bundle unmet rows that satisfy all active policy constraints.
4. Emit deterministic goal rows with:
- `requirement_ids`
- `depends_on`
- `phase_doc_path`
- `allowed_paths`
- `acceptance_commands`
- `required_skills`, `difficulty_score`, `reasoning_tier`
5. Write rows into `goal_checklist` and sync `mapped_goal_ids` in requirement rows.
6. Produce per-goal execution guidance:
- `todo_checklist`
- `risk_notes`
- `parallel_hints`
- `todo_planner` metadata
Use codex-assisted planning when `goal_todo_planner_v1.mode=codex_assisted`; fallback to
rule-only planning if codex is unavailable or disabled.

## Guardrails

- Never generate template-only goals unrelated to unmet requirements.
- Keep `phase_doc_path` in allowed track directory.
- Keep `allowed_paths` minimal and auditable.
- Respect redlines: `contracts/**`, `policies/**`, holdout expansion.
- Keep each phase meaningful: one phase should close one acceptance closure, not one bullet line.
- If bundle criteria fail, keep single-requirement goal as fallback and record reason in goal notes.
