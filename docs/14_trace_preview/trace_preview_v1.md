# CalcTrace Preview v1 (Deterministic Review Evidence)

## Purpose
Before running a full backtest, the kernel produces a small **calc trace preview** as review evidence.

This preview:
- uses **DataCatalog** (enforces `available_at <= as_of`)
- produces a small table for UI review (no backtest execution required)
- helps reviewers see lag/no-lookahead behavior (raw vs lagged signal)
- uses the **same signal compiler** as the backtest adapter, so preview and execution are consistent

## Inputs
- `RunSpec` (uses `segments.test.start/end/as_of`, `extensions.symbols`, `data_snapshot_id`)
- `signal_dsl_v1`
- `variable_dictionary_v1` (provides lag metadata, e.g. `entry_lagged.alignment.lag_bars`)
- `calc_trace_plan_v1` (sample window + variables)

## Outputs
Written under job outputs (pre-run):
`${EAM_JOB_ROOT}/<job_id>/outputs/trace_preview/`
- `calc_trace_preview.csv`
- `trace_meta.json` (rows_before_asof/rows_after_asof, rows_written, as_of, snapshot_id, lag_bars_used, dsl_fingerprint)

Minimum columns (CSV):
- `dt`, `symbol`, `close`, `available_at`
- `eligible` (computed `available_at <= as_of`)
- `entry_raw`, `exit_raw`, `entry_lagged`, `exit_lagged`

Indicator columns (optional, depending on DSL):
- `sma_fast`, `sma_slow` (MA crossover)
- `rsi` (RSI mean reversion)

## Governance Notes
- Preview is not a gate and does not arbitrate pass/fail.
- Holdout is not involved in preview; holdout output restriction remains enforced elsewhere.
