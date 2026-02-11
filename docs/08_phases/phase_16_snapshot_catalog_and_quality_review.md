# Phase 16 — Snapshot Catalog v1 + Quality Review UI/API

## Goal

Add a deterministic, read-only snapshot catalog on top of:

- DataLake snapshot layout
- Phase-15 manifest contracts
- `quality_report.json` evidence

Provide API + UI to review snapshot artifacts and preview data under an `as_of` constraint.

## Scope

- SnapshotCatalog module (read-only, allowlisted snapshot_id)
- JSON API: `/snapshots*`
- UI: `/ui/snapshots*`
- Optional contract: `quality_report_v1`

## Deliverables

- `src/quant_eam/snapshots/catalog.py`
- `src/quant_eam/api/snapshots_api.py`
- UI templates: `snapshots.html`, `snapshot.html`
- Contracts: `contracts/quality_report_schema_v1.json`
- Tests: `tests/test_snapshot_catalog_phase16_api_ui.py`
- Docs:
  - `docs/05_data_plane/snapshot_catalog_v1.md`
  - `docs/10_ui/snapshots_review_ui_v1.md`

## Acceptance

- Container tests pass (offline, tmp_path)
- Snapshot API returns snapshots + preview respects `available_at<=as_of`
- UI pages render 200 and include snapshot_id

## Execution Log

- Start Date: 2026-02-10 (Asia/Taipei)
- End Date: 2026-02-10 (Asia/Taipei)
- Commit: unknown (workspace is not a git repo here)

