# Snapshot Catalog v1 (Review API + Safety Boundary)

Snapshot Catalog is a **read-only** index over DataLake snapshots under `EAM_DATA_ROOT` (default `/data`).
It exists to make snapshot manifests and quality evidence reviewable without reading raw CSV directly.

## Storage Layout (DataLake)

Snapshots live under:

- `<EAM_DATA_ROOT>/lake/<snapshot_id>/`

Key files:

- `manifest.json` (contract: `data_snapshot_manifest_v1`)
- `ingest_manifest.json` (contract: `ingest_manifest_v1`, optional)
- `quality_report.json` (contract: `quality_report_v1`, optional)

## Contracts Validation

Catalog enforces (on load):

- `manifest.json` must validate as `data_snapshot_manifest_v1`
- `ingest_manifest.json` (if present) must validate as `ingest_manifest_v1`
- `quality_report.json` (if present) must validate as `quality_report_v1`

## API (Read-only)

Endpoints:

- `GET /snapshots`
- `GET /snapshots/{snapshot_id}`
- `GET /snapshots/{snapshot_id}/quality`
- `GET /snapshots/{snapshot_id}/preview/ohlcv`

Preview rules:

- Must call `DataCatalog.query_ohlcv` (no direct CSV reads)
- Hard enforcement: `available_at <= as_of`

## Dataset Mapping

Dataset IDs exposed in catalog/query flows should map to:

- `docs/05_data_plane/qa_dataset_registry_v1.json` for dataset semantics
- `docs/05_data_plane/qa_fetch_function_registry_v1.json` for function-to-dataset lineage

This keeps Agent-side `dataset_id` usage deterministic and traceable.

## Security Boundary

- `snapshot_id` is allowlisted (no path traversal).
- API/UI only reads under `EAM_DATA_ROOT` (no arbitrary filesystem reads).
- API is read-only (no writes).
