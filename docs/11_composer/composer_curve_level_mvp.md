# Composer Curve-Level MVP (Sleeve Composition)

## Purpose

The Composer combines multiple **Experience Cards** into a **new composed run** by composing **component equity curves**.

This preserves SSOT:

- **Inputs**: existing dossiers + gate_results + registry cards
- **Arbitration**: only GateResults + Dossier
- **Outputs**: a new append-only dossier + gate_results (+ optional registry card)

## Boundary Rules (Non-Negotiables Applied)

- Policies are **read-only** inputs: the composer only references `policy_bundle_id` and must not inline/override policy params.
- A composed run can be registered (Experience Card) **only if Gate PASS** and evidence references `dossier` + `gate_results`.
- Dossier is **append-only**: rerunning the same composition must be a noop (no overwrites).

## Composition Definition (v1)

### Inputs

- `card_id` list
- `weights` list (same length, non-negative, sum=1.0)

Resolution chain:

1. `card_id` -> registry `card_v1.json`
2. `primary_run_id` -> component dossier directory: `.../dossiers/<run_id>/`
3. Evidence consumed:
   - `curve.csv` (dt,equity)
   - `gate_results.json` (must be contract-valid)

### Alignment Rule

MVP uses **intersection** alignment:

- Compute the set intersection of `dt` across all component curves.
- If intersection is empty: composition is invalid.

Transparency requirement:

- The composed dossier must include `components.json` with `alignment_stats`:
  - per component: `original_points`, `intersection_points`, `drop_ratio`
  - overall: `intersection_points`

### Returns Composition

On the aligned `dt` grid:

- Component returns: `r_i[t] = equity_i[t] / equity_i[t-1] - 1`
- Composed returns: `r[t] = sum_i weight_i * r_i[t]`
- Composed equity:
  - `equity[t0] = 1.0` (fixed base)
  - `equity[t] = equity[t-1] * (1 + r[t])`

### Artifacts Produced

The composed dossier directory includes at least:

- `curve.csv` (dt,equity)
- `metrics.json` (total_return, max_drawdown, sharpe, trade_count=0, adapter_id)
- `trades.csv` (empty stable table; exists for uniformity)
- `components.json` (must exist): component list with `card_id/run_id/weight` and references to component `gate_results`

## Gate Suite For Composition

Composition uses a dedicated gate suite:

- `policies/gate_suite_curve_composer_v1.yaml`
- `policies/policy_bundle_curve_composer_v1.yaml`

Required gates (MVP):

- `basic_sanity` (requires `components.json`)
- `determinism_guard`
- `components_integrity_v1`
  - Each component must have `gate_results.json` present and contract-valid
  - Each component must have `overall_pass=true`
  - Composed curve alignment must be non-empty

Gate configurability (Phase-09P hardening):

- `require_overall_pass` (default true)
- `required_gate_ids` (default empty; when set, each component must pass these gate_id)
- `min_intersection_points` (default 1)

## CLI (MVP)

Run composition (and optionally register a new card on PASS):

```bash
python -m quant_eam.composer.run \
  --card-ids card_<run1>,card_<run2> \
  --weights 0.5,0.5 \
  --policy-bundle policies/policy_bundle_curve_composer_v1.yaml \
  --register-card \
  --title "composed_demo"
```

Output is machine-readable JSON including:

- `run_id`
- `dossier_path`
- `gate_results_path`
- `card_id` (when created)
