# Data Contracts v1 (Manifests + Quality Evidence)

This document formalizes the Data Plane manifests as **versioned contracts** (SSOT for snapshot contents and ingest audit).

## Contracts

### 1) Data Snapshot Manifest

- File: `<EAM_DATA_ROOT>/lake/<snapshot_id>/manifest.json`
- Contract: `contracts/data_snapshot_manifest_schema_v1.json`
- `schema_version`: `data_snapshot_manifest_v1`

Purpose:

- Snapshot SSOT: dataset file paths, row counts, symbols, time bounds, and sha256 evidence.
- Must be deterministic and replayable.

Key fields:

- `snapshot_id`, `created_at`
- `datasets[]`:
  - `dataset_id`, `file`, `row_count`, `fields`, `symbols`
  - `dt_min/dt_max`, `available_at_min/available_at_max`
  - `sha256`
  - `extensions.quality_report_ref` (path to quality evidence)

### 2) Ingest Manifest

- File: `<EAM_DATA_ROOT>/lake/<snapshot_id>/ingest_manifest.json`
- Contract: `contracts/ingest_manifest_schema_v1.json`
- `schema_version`: `ingest_manifest_v1`

Purpose:

- Auditable record of the ingest request and the produced snapshot outputs.

Key fields:

- `provider_id` (e.g. `mock`, `wequant`)
- `request_spec` (symbols/start/end/frequency)
- `rows_written`, `sha256_of_data_file`
- `output_paths.*` including `quality_report`

## Data Quality Evidence (v1)

DataLake writes:

- `<EAM_DATA_ROOT>/lake/<snapshot_id>/quality_report.json`

This report is deterministic evidence including:

- rows before/after dedupe
- duplicate_count
- null_count_by_col
- min/max for open/high/low/close/volume

The snapshot manifest references it via `datasets[].extensions.quality_report_ref`.

Quality report contract:

- `schema_version`: `quality_report_v1`
- contract: `contracts/quality_report_schema_v1.json`

## 3) Agents Plane Registries

Data function/dataset contracts for agent runtime:

- `docs/05_data_plane/qa_fetch_function_registry_v1.json`
  - `schema_version`: `qa_fetch_function_registry_v1`
  - frozen function baseline from v3 matrix
- `docs/05_data_plane/qa_dataset_registry_v1.json`
  - `schema_version`: `qa_dataset_registry_v1`
  - dataset semantics for `query_dataset(...)` and as_of policy

Usage reference:

- `docs/05_data_plane/agents_plane_data_contract_v1.md`
