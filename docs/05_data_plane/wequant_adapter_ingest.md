# WeQuant Adapter Ingest (Phase-03B)

Legacy note: this document is adapter-specific historical reference.
Agents Plane primary contracts are `source=fetch` + `engine=mongo|mysql`.

This adapter **only** performs ingest into DataLake snapshots. It does not backtest, arbitrate, or evaluate strategy
validity.

Policies are governance inputs and are treated as **read-only**. The adapter consumes `policy_bundle_v1.yaml` and uses
the referenced `asof_latency_policy_v1` to enforce the as-of semantics.

## Responsibilities (Boundary)

- Fetch raw OHLCV data from WeQuant (or a fake offline client)
- Normalize to the project’s minimal `ohlcv_1d` columns
- Generate or validate `available_at` using `asof_latency_policy_v1`
- Write:
  - snapshot dataset CSV
  - snapshot manifest (Phase-03 DataLake MVP)
  - ingest manifest (auditable record of ingest)

## Output Layout (compatible with Phase-03)

Under `<EAM_DATA_ROOT>/lake/<snapshot_id>/`:

- `ohlcv_1d.csv`
- `manifest.json`
- `ingest_manifests/ohlcv_1d_wequant_ingest.json`

## Column Mapping (minimum)

Written to CSV:

- `symbol` (str)
- `dt` (YYYY-MM-DD or ISO datetime)
- `open`, `high`, `low`, `close` (float)
- `volume` (float)
- `available_at` (ISO datetime with timezone, required)
- `source` (always `"wequant"` for this adapter)

Dedup rule:

- `(symbol, dt)` must be unique; duplicates are dropped and counted in the ingest manifest.

## `available_at` Rules (policy-driven)

The as-of semantics is fixed by policy:

- `asof_rule == "available_at<=as_of"`

If the source provides `available_at`:

- keep it, but validate:
  - non-empty
  - parseable ISO datetime
  - `available_at >= dt` (dt interpreted as bar close timestamp)

If the source does not provide `available_at`:

- generate:
  - `bar_close_ts`:
    - if `dt` is `YYYY-MM-DD`, interpret as **16:00:00 Asia/Taipei (+08:00)** (daily bar close anchor)
    - if `dt` is datetime, treat as bar close timestamp (tz-naive assumed +08:00)
  - `available_at = bar_close_ts + default_latency_seconds + bar_close_to_signal_seconds`

## CLI

Offline demo (no wequant dependency):

```bash
docker compose run --rm api python -m quant_eam.wequant_adapter.ingest \
  --client fake \
  --snapshot-id demo_wq_001 \
  --dataset-id ohlcv_1d \
  --symbols AAA,BBB \
  --start 2024-01-01 \
  --end 2024-01-10 \
  --policy-bundle policies/policy_bundle_v1.yaml
```

Real client (requires `wequant` installed/configured; secrets must not be stored in repo):

```bash
docker compose run --rm api python -m quant_eam.wequant_adapter.ingest \
  --client real \
  --snapshot-id wq_real_001 \
  --dataset-id ohlcv_1d \
  --symbols 2330.TW,2317.TW \
  --start 2024-01-01 \
  --end 2024-02-01 \
  --policy-bundle policies/policy_bundle_v1.yaml
```

If `wequant` is not available, the CLI will instruct you to use `--client fake`.
