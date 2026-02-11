# Param Sweep v1 (Budgeted Grid Search)

Phase: 23

## Purpose

Provide a deterministic, budget-governed parameter sweep (grid search) at the workflow layer, without leaking holdout details.

This is a workflow feature:

- It does not change kernel arbitration logic.
- It writes evidence under the **job outputs** directory, and links to run dossiers as evidence.

## SweepSpec (Input)

SweepSpec may be embedded in:

- `job_spec.extensions.sweep_spec` (preferred), or
- `blueprint.extensions.sweep_spec` (convenient for `/jobs/blueprint` submissions).

Fields (v1):

- `param_grid`: object of `param_name -> [values...]`
- `metric`: `"sharpe" | "total_return" | "max_drawdown"` (default: `sharpe`)
- `higher_is_better`: boolean (default: `true`)
- Optional:
  - `max_trials`: int (workflow may reduce trials; never increases beyond budget policy)
  - `budget_policy_path`: path to `budget_policy_v1` asset (default: `policies/budget_policy_v1.yaml`)

Param application rule:

- Each grid combination overrides `signal_dsl_v1.params` (declarative only).
- Policies remain read-only references (no inline overrides).

## Budget Enforcement

Budget is enforced using `budget_policy_v1`:

- `params.max_proposals_per_job` is used as the default upper bound for sweep trials (v1 reuses this budget knob).
- Optional early stop: `params.stop_if_no_improvement_n` (stop after N consecutive non-improving eligible trials).

When sweep stops due to budget/stop, the workflow appends a `STOPPED_BUDGET` JobEvent with `{reason, limit, counters}`.

## Evidence (Append-Only)

Written under:

`jobs/<job_id>/outputs/sweep/`

- `trials.jsonl` (append-only): one JSON object per candidate:
  - `params`, `run_id`, `dossier_path`, `test_metric`, `overall_pass`, `holdout_pass_minimal`
- `leaderboard.json` (written once at sweep completion):
  - references best candidate and top-K, by **test metric only**

Contracts (optional, for validation):

- `contracts/sweep_trial_schema_v1.json` (each line of `trials.jsonl`)
- `contracts/leaderboard_schema_v1.json` (`leaderboard.json`)

## Selection Rule (Anti Holdout Contamination)

- Best candidate selection uses **test** metric only.
- Holdout is **filter-only** (pass/fail + minimal summary only).
- Holdout internals (curve/trades/full metrics) must not be written into job outputs.

## Spawn Best

API:

- `POST /jobs/{job_id}/spawn_best`

Behavior:

- Spawns a new child job with `blueprint.strategy_spec.params` updated to the selected best `params`.
- Enforces `budget_policy_v1` spawn budgets (same semantics as improvement spawn):
  - `max_spawn_per_job`
  - `max_total_iterations` (lineage depth)
- Child job returns to `WAITING_APPROVAL(step=blueprint)` for human review.

