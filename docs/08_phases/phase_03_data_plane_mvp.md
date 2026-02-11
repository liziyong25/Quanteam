# Phase-03: Data Plane MVP (Snapshots + Time-Travel as_of)

## 1) 目标（Goal）

- Land a deterministic DataLake snapshot format with manifest (CSV + JSON).
- Provide DataCatalog time-travel query with hard enforcement: `available_at <= as_of`.
- Use demo (locally generated) data to validate protocol and replayability. No wequant dependency.

## 2) 背景（Background）

If data access is not governed and replayable:

- Lookahead leaks happen silently (future data used in past decisions).
- Runs cannot be reproduced (no stable snapshot + manifest).
- UI/review cannot audit evidence sources.

## 3) 范围（Scope）

### In Scope

- `src/quant_eam/data_lake/**`: snapshot writer + demo ingest CLI
- `src/quant_eam/datacatalog/**`: time-travel query + CLI
- Tests validating reproducibility and `as_of` enforcement
- Minimal docs for the data plane MVP

### Out of Scope

- No real data vendor ingestion (wequant comes in Phase-03B).
- No compiler/runner/backtest/gates.

## 4) 实施方案（Implementation Plan）

- Snapshot is written under `<EAM_DATA_ROOT>/lake/<snapshot_id>/`.
- Dataset `ohlcv_1d` is stored as CSV with required `available_at` column.
- If `available_at` is missing on write, generate it from `policies/asof_latency_policy_v1.yaml`.
- DataCatalog queries enforce `available_at <= as_of` and stable sorting.

## 5) 交付物（Deliverables）

- DataLake:
  - `src/quant_eam/data_lake/lake.py`
  - `src/quant_eam/data_lake/demo_ingest.py`
- DataCatalog:
  - `src/quant_eam/datacatalog/catalog.py`
  - `src/quant_eam/datacatalog/query.py`
- Docs:
  - `docs/05_data_plane/data_plane_mvp.md`

## 6) 验收标准（Acceptance / DoD）

- Build:
  - `docker compose build api worker`
- Tests:
  - `docker compose run --rm api pytest -q`
- Demo ingest + query:
  - `docker compose run --rm api python -m quant_eam.data_lake.demo_ingest --snapshot-id demo_snap_001`
  - `docker compose run --rm api python -m quant_eam.datacatalog.query --snapshot-id demo_snap_001 --as-of 2024-01-05T00:00:00+08:00 --symbols AAA,BBB`
- Docs gate:
  - `python3 scripts/check_docs_tree.py`

## 7) 完成记录（Execution Log）

- Start Date: 2026-02-09 (Asia/Taipei)
- End Date: 2026-02-09 (Asia/Taipei)
- PR/Commit: unknown (repo is not a git repository; `git rev-parse --short HEAD` fails)
- Notes:
  - Added deterministic snapshot writer + manifest and a demo ingest generator
  - Added DataCatalog time-travel query enforcing `available_at <= as_of`
  - Tests cover reproducibility, as_of filtering, and policy-driven available_at generation

## 8) Codex Prompt Footer

Append `docs/_snippets/codex_phase_footer.md` to the phase task card prompt for consistency.

