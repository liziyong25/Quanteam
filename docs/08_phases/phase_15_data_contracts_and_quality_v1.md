# Phase 15 — Data Contracts + Data Quality Gates v1

## Goal

Formalize Data Plane manifests as versioned contracts and emit deterministic data quality evidence after ingest/write.

## Scope

- Add manifest contracts:
  - `data_snapshot_manifest_v1`
  - `ingest_manifest_v1`
- Extend `python -m quant_eam.contracts.validate` to dispatch these schema_versions.
- DataLake writes `quality_report.json` and references it from `manifest.json`.
- Ingest writes `ingest_manifest.json` and validates it against contracts.

## Deliverables

- `contracts/data_snapshot_manifest_schema_v1.json`
- `contracts/ingest_manifest_schema_v1.json`
- `src/quant_eam/data_lake/lake.py` quality report + manifest self-validate
- `src/quant_eam/ingest/wequant_ohlcv.py` ingest manifest contract + validation
- Tests: `tests/test_data_contracts_quality_phase15.py`
- Docs: `docs/05_data_plane/data_contracts_v1.md`

## Acceptance

- Docker build ok
- Container `pytest -q` all green
- `contracts.validate` passes for both manifests
- `quality_report.json` exists and is referenced

## Execution Log

- Start Date: 2026-02-10 (Asia/Taipei)
- End Date: 2026-02-10 (Asia/Taipei)
- Commit: unknown (workspace is not a git repo here)

