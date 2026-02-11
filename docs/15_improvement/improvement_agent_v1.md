# ImprovementAgent v1 (Mock, Deterministic)

## Purpose

ImprovementAgent generates **candidate** Blueprint drafts based on **structured evidence** from:

- `gate_results.json` (GateResults SSOT for pass/fail)
- `report_summary.json` (structured report summary)

It does **not** arbitrate validity and must not write to dossier/registry directly.

## Inputs / Outputs

**Input (Orchestrator-built):**

- base job id / run id
- a Blueprint (v1) as the proposal base (usually `blueprint_final.json`)
- GateResults (v1)
- Report summary (JSON)
- Budget policy (v1) (read-only governance input)

**Outputs (append-only artifacts under job outputs):**

- `improvement_proposals.json` (contract: `improvement_proposals_v1`)
- `agent_run.json` (contract: `agent_run_v1`)

## Governance Rules (Non-Negotiable)

- No external LLM in tests: `provider="mock"` must be deterministic.
- Proposals are **declarative**: must remain in Blueprint/DSL form.
- Policies are **read-only references**: do not inline/override policy params in proposals.
- Proposals/extensions must not act as executable "override switches" for execution/cost/asof/risk; changes are expressed only via governed ids (e.g. `policy_bundle_id`) inside the Blueprint draft itself.
- Enforcement:
  - Orchestrator enforces budgets (proposal count, spawn limits, iteration depth).
  - UI shows proposals and allows spawning a new job; spawning returns to Blueprint review checkpoint.

## Budget/Stop

`budget_policy_v1` limits:

- `max_proposals_per_job`
- `max_spawn_per_job`
- `max_total_iterations`

See: `docs/04_policies/budget_policy_v1.md` and `docs/16_budget_stop/budget_policy_v1.md`.
