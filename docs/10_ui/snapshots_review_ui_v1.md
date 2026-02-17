# Snapshots Review UI v1 (Read-only)

This UI provides a minimal, read-only console to review DataLake snapshots and data quality evidence.

## Pages

1) `/ui/snapshots`

- List snapshots:
  - snapshot_id
  - created_at
  - dataset summary
  - flags: has quality / has ingest manifest

2) `/ui/snapshots/{snapshot_id}`

- Show:
  - `manifest.json` (formatted)
  - `ingest_manifest.json` (if present)
  - `quality_report.json` (if present, plus key metrics)
- Provide an **as_of preview** form for `ohlcv_1d`:
  - symbols/start/end/as_of/limit
  - preview is served via DataCatalog (enforces `available_at<=as_of`)

## SSOT Rules

- UI renders only structured files (manifests/quality report) plus DataCatalog preview results.
- UI does not write or mutate artifacts.

