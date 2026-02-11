# Data Plane MVP (Phase-03)

This document defines the minimal, executable data plane for Quant-EAM:

- Deterministic snapshots written by DataLake
- Time-travel queries via DataCatalog
- Hard enforcement of `available_at <= as_of` (no lookahead)

Policies are governance inputs and are treated as read-only.

## Snapshot Layout

Data root comes from env `EAM_DATA_ROOT` (container default: `/data`).

Snapshot paths:

- `<root>/lake/<snapshot_id>/ohlcv_1d.csv`
- `<root>/lake/<snapshot_id>/manifest.json`

Manifest schema version (internal to Phase-03):

- `data_snapshot_manifest_v1`

## Dataset: `ohlcv_1d` (Minimum)

CSV columns (minimum):

- `symbol` (str)
- `dt` (YYYY-MM-DD or ISO datetime)
- `open`, `high`, `low`, `close` (float)
- `volume` (float)
- `available_at` (ISO datetime with timezone, required)

### `dt` interpretation (deterministic)

If `dt` is a date string (`YYYY-MM-DD`), it is interpreted as the trading day and anchored at
**16:00:00 Asia/Taipei (+08:00)** as the bar close timestamp.

If `dt` is an ISO datetime, it is treated as the bar close timestamp (tz-naive values are assumed +08:00).

## `available_at` generation (policy-driven)

If ingest input rows do not include `available_at`, DataLake generates it using:

- policy: `policies/asof_latency_policy_v1.yaml`
- fixed semantics: `params.asof_rule == "available_at<=as_of"`
- generation:
  - `available_at = bar_close_ts + default_latency_seconds + bar_close_to_signal_seconds`

## Time-Travel Query (`as_of`)

DataCatalog enforces:

- Only rows with `available_at <= as_of` are returned
- Filtering by `symbols`, `start`, `end`
- Stable sorting by `(symbol, dt)`

