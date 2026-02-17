# Budget Policy v1

**Asset:** `policies/budget_policy_v1.yaml`  
**Type:** governance input (read-only)  
**Produced by:** Governance/Repo maintainers  
**Consumed by:** Orchestrator/Workflow layer (job advancement, proposal generation, spawn limits)

## Purpose

`budget_policy_v1` defines **hard limits** to prevent infinite iteration loops and uncontrolled “proposal spam”.
It is a Kernel governance input: jobs/modules must **not inline or override** budget values.

## Key Fields

- `policy_id` (string, required): stable identifier; referenced by id only.
- `policy_version` (enum, required): must be `"v1"`.
- `params.max_proposals_per_job` (int, required): upper bound for ImprovementAgent outputs for a single job.
- `params.max_spawn_per_job` (int, required): upper bound for how many child jobs can be spawned from a single base job.
- `params.max_total_iterations` (int, required): upper bound for iteration depth (root job iteration is `0`).
- `params.stop_if_no_improvement_n` (int, optional): optional stop knob (exact semantics are defined by Orchestrator docs).

## Prohibitions

- Budget policy must not be embedded into Blueprint/DSL/Runner config.
- Agents must not bypass budgets by emitting executable scripts; only declarative artifacts are allowed.

## Examples

- Default asset: `policies/budget_policy_v1.yaml`

