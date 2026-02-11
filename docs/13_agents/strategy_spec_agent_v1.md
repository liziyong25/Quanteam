# StrategySpecAgent v1 (Blueprint Draft -> StrategySpec + Trace Plan)

## Purpose
After a Blueprint draft is approved, StrategySpecAgent generates the strategy specification artifacts used for review and trace preview:
- `signal_dsl_v1` (declarative strategy DSL)
- `variable_dictionary_v1` (variable graph + lag metadata)
- `calc_trace_plan_v1` (what to preview and render)
- `blueprint_final.json` (still `blueprint_v1`, with `strategy_spec` filled)

## Inputs
- Approved `blueprint_draft.json` (must validate `blueprint_v1`)
- The originating `idea_spec_v1` (intent context; not executable)

Provider:
- Tests use `provider="mock"` (deterministic, offline).

## Outputs (must validate)
Written under: `${EAM_JOB_ROOT}/<job_id>/outputs/agents/strategy_spec/`
- `blueprint_final.json` (`blueprint_v1`)
- `signal_dsl.json` (`signal_dsl_v1`)
- `variable_dictionary.json` (`variable_dictionary_v1`)
- `calc_trace_plan.json` (`calc_trace_plan_v1`)
- `agent_run.json` (`agent_run_v1`)

## Non-Negotiables
- No executable scripts, no bypassing Compiler/Runner.
- Policies are referenced by id only (`policy_bundle_id`), never inlined.
- `extensions` are metadata only.

