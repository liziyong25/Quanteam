# GateRunner v1

GateRunner consumes a dossier and read-only policies, runs deterministic gates, and writes `gate_results.json`.

## Inputs

- `--dossier <dir>`: dossier directory under `${EAM_ARTIFACT_ROOT}/dossiers/<run_id>/`
  - Must include at least: `dossier_manifest.json`, `config_snapshot.json`, `metrics.json`, `curve.csv`, `trades.csv`
- `--policy-bundle <path>`: `policies/policy_bundle_v1.yaml` (read-only)

GateRunner resolves all policy assets from the **same directory** as the bundle file.

## Output

- `<dossier_dir>/gate_results.json` (append-only)
  - Contract: `contracts/gate_results_schema_v1.json`
  - If `gate_results.json` already exists: default behavior is no-op (exit 0, no rewrite)

## Determinism

Given the same:

- dossier directory contents
- policies directory contents
- code version

GateRunner must produce identical `gate_results.json` bytes.

## Holdout Restriction

GateRunner enforces:

- `gate_suite_v1.params.holdout_policy.output == "pass_fail_minimal_summary"`
- Holdout evaluation output is restricted (see `docs/08_gates/holdout_vault_v1.md`)

## Exit Codes

- `0`: OK (gate results written, or no-op if already exists)
- `2`: INVALID (policy invalid, unsupported gate, dossier missing key evidence, holdout output violation)
- `1`: usage/error (missing args, file not found, parse errors)

