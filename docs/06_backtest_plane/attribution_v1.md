# Attribution + Diagnostics v1 (Phase-24)

This document specifies deterministic, dossier-backed performance attribution and diagnostics evidence.

## Goals

- Provide a reviewable answer to "why did this run make/lose money" without external data dependencies.
- Keep outputs deterministic and sourced from dossier artifacts (SSOT, append-only).
- Preserve governance boundaries: costs come only from `cost_policy_v1` (no strategy inline overrides).

## Evidence Artifacts (Dossier SSOT)

Written under `artifacts/dossiers/<run_id>/`:

- `attribution_report.json`
  - Machine-readable attribution summary (deterministic).
- `reports/attribution/report.md`
  - Human-readable report that references fields in `attribution_report.json` and dossier artifact paths.

These are append-only dossier artifacts: writers must not overwrite existing files.

## attribution_report.json (MVP)

Key sections:

- `returns`
  - `net_return`: derived from `curve.csv` (`equity_last/equity_first - 1`)
  - `gross_return`: deterministic recompute with `commission_bps=0` and `slippage_bps=0` using the same adapter + signals when possible
  - `cost_drag`: `gross_return - net_return` (if gross available)
- `contribution_by_symbol`
  - Per-symbol PnL attribution from `trades.csv` (when present)
- `contribution_by_timebucket`
  - Monthly/weekly buckets (prefer trade exit buckets; otherwise fall back to equity-curve returns buckets)
- `drawdown`
  - `max_drawdown`, `dd_duration_bars`, minimal `top_dd_points`
- `trades`
  - win/loss stats and a small list of top/worst trades (from `trades.csv`)
- `sensitivity.cost_x2_recompute`
  - Deterministic recompute with doubled `commission_bps` and `slippage_bps` (from policy)
- `evidence_refs`
  - Stable relative paths (e.g. `curve.csv`, `trades.csv`, `metrics.json`)

## Determinism / No External Dependencies

- No network IO.
- Recompute uses `DataCatalog` (local lake CSVs) and policies loaded from the repo `policies/` directory.
- Timestamps are deterministic in tests via `SOURCE_DATE_EPOCH`.

