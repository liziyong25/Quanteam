# HoldoutVault v1 (Minimal)

HoldoutVault is the mechanism used by GateRunner to evaluate the holdout segment while enforcing the hard boundary:

- holdout output must be **pass/fail + minimal summary only**
- do not write holdout curves/trades or detailed metrics into the dossier

This implements the governance rule:

- `gate_suite_v1.params.holdout_policy.output == "pass_fail_minimal_summary"`

## What HoldoutVault Does

- Reads holdout segment from `config_snapshot.json` (runspec)
- Queries data via DataCatalog (so `available_at <= as_of` is enforced)
- Runs the adapter in-memory
- Returns only:
  - `pass: bool`
  - `summary: string` (1-2 lines)
  - `metrics_minimal` (optional, must stay minimal)

GateRunner writes this to `gate_results.json` as top-level `holdout_summary`.

## What HoldoutVault Must Never Do

- Write any of these into the dossier:
  - holdout equity curve files
  - holdout trades files
  - per-bar or per-trade detailed diagnostics
- Provide holdout internals that can be used for iterative tuning loops.

## Where It Is Implemented

- Code: `src/quant_eam/holdout/vault.py`
- Gate: `gate_holdout_passfail_v1` in `src/quant_eam/gates/holdout_passfail.py`

