# Gates (v1)

Gates are deterministic checks that produce arbitration evidence derived from:

- Dossier artifacts (SSOT evidence bundle)
- Policies (read-only governance input via `policy_bundle_v1.yaml`)

Output is a **contract-validated** gate results file:

- Contract: `contracts/gate_results_schema_v1.json` (`schema_version="gate_results_v1"`) or `contracts/gate_results_schema_v2.json` (`schema_version="gate_results_v2"`)
- Location: `<dossier_dir>/gate_results.json`

## Core Rules (SSOT)

- Policies are read-only references by id. GateRunner must not modify policy files.
- PASS/FAIL must reference dossier artifacts (evidence chain).
- Holdout output is restricted: pass/fail + minimal summary only (no curves/trades).
- Append-only: if `gate_results.json` already exists, GateRunner is a no-op by default.

## GateRunner v1

CLI:

```bash
python -m quant_eam.gaterunner.run --dossier /artifacts/dossiers/<run_id> --policy-bundle policies/policy_bundle_v1.yaml
```

GateRunner reads `gate_suite_id` from the policy bundle and loads the suite policy from the same policies directory (v1 assets):

- `policies/gate_suite_v1.yaml` (must match the bundle `gate_suite_id`)
- `params.holdout_policy.output` must equal `pass_fail_minimal_summary`

## Minimal Gates Implemented (v1)

GateRunner supports these gate ids/versions:

- `data_snapshot_integrity_v1` / `v1`: validates snapshot manifest/quality_report contracts and sha256 anti-tamper integrity
- `basic_sanity` / `v1`: core dossier artifacts exist
- `determinism_guard` / `v1`: config_snapshot contains replay metadata (runspec + policy sha256 map)
- `gate_no_lookahead_v1` / `v1`: re-query DataCatalog and verify `available_at <= as_of` enforcement
- `gate_delay_plus_1bar_v1` / `v1`: stress test with lag + 1 bar (in-memory rerun)
- `gate_cost_x2_v1` / `v1`: stress test with costs x2 (in-memory rerun; must not write policies)
- `gate_holdout_passfail_v1` / `v1`: holdout evaluation via HoldoutVault restricted output
- `holdout_leak_guard_v1` / `v1`: scan iteration-facing artifacts for second-order holdout numeric leakage (Phase-27)

Docs:

- `docs/08_gates/data_snapshot_integrity_v1.md`

Each gate result records:

- `pass` and minimal `metrics`
- optional `thresholds`
- optional `evidence` with referenced dossier artifacts

## Contract Notes: `gate_results_v1`

- `results[]` is the authoritative list of gate outcomes.
- `holdout_summary` (when present) is the **only** holdout surface:
  - `pass: bool`
  - `summary: string` (1-2 lines)
  - `metrics_minimal: object` (optional, must stay minimal)

## Contract Notes: `gate_results_v2`

v2 closes the schema gap around per-segment gate outputs:

- `segment_results[]` is explicit (no longer hidden under `extensions`).
