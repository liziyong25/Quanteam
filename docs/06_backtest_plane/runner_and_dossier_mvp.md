# Runner + Dossier MVP (Phase-04)

## Runner Inputs

Runner consumes:

- RunSpec v1 JSON (validated against contracts)
- `policy_bundle_v1.yaml` (read-only governance input)
- `snapshot_id` (DataLake snapshot) and segment `as_of`

## Determinism & No Bypass

- Data access is only via DataCatalog (enforces `available_at <= as_of`).
- Policies are read-only, referenced by id, and their sha256 are recorded in `config_snapshot.json`.
- `run_id` is derived deterministically from canonical RunSpec JSON sha256 (first 12 hex).

## Dossier (Append-only evidence bundle)

Written under `${EAM_ARTIFACT_ROOT}/dossiers/<run_id>/`:

- `dossier_manifest.json` (must validate against `contracts/dossier_schema_v1.json`)
- `config_snapshot.json` (runspec + policy ids + sha256 + env/deps)
- `data_manifest.json` (snapshot manifest reference/copy)
- `metrics.json`
- `curve.csv`
- `trades.csv`
- `reports/report.md`

Append-only behavior:

- If the dossier directory already exists, runner performs a no-op and returns success (`--if-exists noop`).

## CLI (Demo)

Offline demo (uses Phase-03 demo snapshot generator):

```bash
docker compose run --rm api python -m quant_eam.runner.run --demo --policy-bundle policies/policy_bundle_v1.yaml
```

