# WeQuant Ingest Adapter v1 (DataLake Snapshot)

This document defines the **DataLake ingest adapter** for WeQuant-style OHLCV inputs.

## Scope / Non-Goals

- Scope: ingest `ohlcv_1d` into a deterministic DataLake snapshot + manifests.
- Non-goals: DataCatalog queries, backtests, gates, workflow automation.

## Provider Abstraction

The ingest adapter supports a provider interface:

- `mock` provider: deterministic, offline (used by tests/CI).
- `wequant` provider: optional real integration path (not used by tests; may require credentials/runtime env).

Provider output minimum columns:

- `symbol`, `dt`, `open`, `high`, `low`, `close`, `volume`
- `available_at` is optional; if missing, DataLake will generate it from policy.

## `available_at` (Policy-Driven)

If the provider does not provide `available_at`, DataLake fills it using:

- `policies/asof_latency_policy_v1.yaml`
- fixed semantics: `available_at<=as_of`

See: `docs/04_policies/asof_latency_policy_v1.md`.

## `dt` Semantics / Timezone (Hard Rules)

Adapter output is normalized for deterministic replay:

- `ohlcv_1d.csv.dt` is always written as `YYYY-MM-DD` (trading day string).
- Trading day is anchored at **16:00:00 Asia/Taipei (+08:00)** as the bar close timestamp (same as DataLake/DataCatalog).

If a provider returns a datetime-like `dt` (ISO string or datetime object), the ingest adapter must:

- normalize it into a trading day string `YYYY-MM-DD` (using +08:00 for tz-naive values)
- record the original dt source kind into `ingest_manifest.json.extensions` (metadata only)
- fail (exit=2) if `dt` cannot be parsed/normalized

## CLI

Ingest OHLCV into a DataLake snapshot:

```bash
python -m quant_eam.ingest.wequant_ohlcv \
  --provider mock \
  --snapshot-id demo_wq_snap_001 \
  --symbols AAA,BBB \
  --start 2024-01-01 --end 2024-01-10
```

`--root` defaults to `EAM_DATA_ROOT` (container default: `/data`).

## Outputs

Snapshot layout (under `<root>/lake/<snapshot_id>/`):

- `ohlcv_1d.csv`
- `manifest.json` (DataLake snapshot manifest)
- `ingest_manifest.json` (adapter audit manifest)

`ingest_manifest.json` is a contracts SSOT (v1). It must include:

- snapshot_id/provider/symbols/time_range
- sha256 of the written dataset file
- as-of audit fields derived from read-only policy assets:
  - `asof_latency_policy_id`
  - `asof_rule` (fixed: `available_at<=as_of`)
  - `default_latency_seconds`
  - optional `trade_lag_bars_default`

Contract validate:

```bash
python -m quant_eam.contracts.validate <root>/lake/<snapshot_id>/ingest_manifest.json
```

## Real Provider Failure Mode (Stub)

- Tests/CI always use `--provider mock` (offline deterministic).
- If `--provider wequant` is requested but `wequant` is not available or not integrated:
  - CLI exits with code `2`
  - stderr instructs to use `--provider mock` or install/configure wequant for manual runs
