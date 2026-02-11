# Gate: `data_snapshot_integrity_v1`

Purpose: prevent silent data tampering / inconsistency by treating DataLake snapshot evidence as a deterministic Gate input.

This gate is **read-only** and does **not** write anything to `/data`. It only reads:

- `EAM_DATA_ROOT/lake/<snapshot_id>/manifest.json`
- `EAM_DATA_ROOT/lake/<snapshot_id>/ingest_manifest.json` (optional)
- `EAM_DATA_ROOT/lake/<snapshot_id>/quality_report.json` (required)
- the dataset CSV referenced by the manifest (e.g. `ohlcv_1d.csv`)

## Who Runs / Who Consumes

- Producer: `quant_eam.gaterunner` executes this gate as part of a gate suite.
- Consumers: Kernel/Registry/UI (via `gate_results.json`) treat this as part of the arbitration evidence chain.

## Deterministic Rules (v1)

1. **Contract validation**
   - `manifest.json` must validate as `data_snapshot_manifest_v1`
   - `ingest_manifest.json` (if present) must validate as `ingest_manifest_v1`
   - `quality_report.json` must validate as `quality_report_v1` (compat: `data_quality_report_v1` accepted)

2. **Integrity (anti-tamper)**
   - Recompute `sha256(ohlcv_1d.csv)` and it must equal:
     - `manifest.datasets[].sha256`
     - `ingest_manifest.sha256_of_data_file` (if ingest_manifest exists)

3. **Minimal self-consistency**
   - `quality_report.rows_after_dedupe == manifest.datasets[].row_count`
   - `dt_min/dt_max` and `available_at_min/available_at_max` must not contradict between manifest and quality_report

If `ingest_manifest.json` is missing, the gate records `missing_ingest_manifest=true` but can still pass if the other checks pass.

## How To Enable (v2 gate suite / bundle)

This repo keeps v1 policy assets immutable. To enable snapshot integrity verification without modifying `*_v1.yaml`,
use the provided v2 bundle:

- Gate suite: `policies/gate_suite_v2_snapshot_integrity.yaml` (policy_id `gate_suite_v1_snapshot_integrity_default_v2`)
- Policy bundle: `policies/policy_bundle_v2_snapshot_integrity.yaml` (policy_bundle_id `policy_bundle_v1_default_snapshot_integrity_v2`)

Example:

```bash
python -m quant_eam.gaterunner.run \
  --dossier /artifacts/dossiers/<run_id> \
  --policy-bundle policies/policy_bundle_v2_snapshot_integrity.yaml
```

