# Phase 14 — Real Data Ingest MVP (WeQuant Adapter -> DataLake Snapshot)

## Goal

Add a deterministic ingest adapter that can write WeQuant-style OHLCV into DataLake snapshots, producing:

- snapshot dataset CSV
- DataLake `manifest.json`
- adapter `ingest_manifest.json`

Tests use a mock provider (offline, deterministic). A real provider path exists but is optional.

## Scope

- New module: `quant_eam.ingest.wequant_ohlcv`
- Provider abstraction: mock + optional real
- Offline unit tests verifying reproducibility + as_of filtering behavior via DataCatalog

## Deliverables

- Code: `src/quant_eam/ingest/wequant_ohlcv.py`
- Docs: `docs/05_data_plane/wequant_ingest_adapter_v1.md`
- Tests: `tests/test_ingest_phase14_wequant_adapter_mvp.py`

## Acceptance

- `docker compose build api worker`
- container `pytest -q` all green
- demo ingest (mock provider) + datacatalog query works

## Execution Log

- Start Date: 2026-02-10 (Asia/Taipei)
- End Date: 2026-02-10 (Asia/Taipei)
- Commit: unknown (workspace is not a git repo here)

