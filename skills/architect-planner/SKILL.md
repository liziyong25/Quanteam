---
name: architect-planner
description: Run mandatory pre-plan architecture review before goal publish. Use when controller must read requirement sources, decide skeleton-first/impl-after ordering, produce requirement and goal priority, and emit bundle/parallel hints for dispatch.
---

# Architect Planner

## Workflow

1. Read requirement sources configured in `planning_policy_v2.architect_preplan_v1.source_documents`.
2. Build unmet requirement set and active goal set.
3. Enforce architecture ordering:
- Skeleton interface requirements first.
- Impl requirements only after skeleton dependencies are ready.
4. Output pre-plan artifact with:
- `requirement_priority`
- `goal_priority`
- `bundle_hints`
- `parallel_hints`
- `rationale`
5. Feed priority order into scheduler before generating/publishing new goals.

## Guardrails

- Do not publish tasks before pre-plan stage finishes.
- Keep bundle hints dependency-safe (same parent signature unless policy allows otherwise).
- Keep parallel hints constrained by `allowed_paths` disjointness.
- Respect redlines: `contracts/**`, `policies/**`, holdout visibility expansion.

## Fallback

- If codex-assisted planning is unavailable, use deterministic rule-based planning.
- If `require_codex_for_preplan=true`, mark pre-plan blocked and stop goal generation.
