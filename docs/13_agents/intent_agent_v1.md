# IntentAgent v1 (IdeaSpec -> Blueprint Draft)

## Boundary
IntentAgent produces a **declarative Blueprint draft**. It must not produce executable scripts or bypass the Compiler/Kernel.

## Input
- `IdeaSpec` (v1): `contracts/idea_spec_schema_v1.json`

Key fields:
- `snapshot_id`: recorded into blueprint extensions for workflow determinism
- `policy_bundle_path`: used read-only to resolve `policy_bundle_id`

## Output
- `Blueprint` (v1): must validate against `contracts/blueprint_schema_v1.json`
- Stored at: `${EAM_JOB_ROOT}/<job_id>/outputs/agents/intent/blueprint_draft.json`

## Handoff (to StrategySpecAgent)
- This blueprint is **a draft** for review.
- After approval, `StrategySpecAgent v1` may generate:
  - `signal_dsl_v1` (strategy_spec)
  - `variable_dictionary_v1`
  - `calc_trace_plan_v1`
  - and a `blueprint_final.json` that still validates as `blueprint_v1`.

## Policy Rules
- Policies are read-only: blueprint must reference `policy_bundle_id` only.
- `extensions` are metadata only; must not override execution/cost parameters.
