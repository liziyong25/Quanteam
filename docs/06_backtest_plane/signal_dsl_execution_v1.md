# Signal DSL Execution v1 (vectorbt_signal_v1 adapter)

This document defines the executable subset of `signal_dsl_v1` supported by the `vectorbt_signal_v1` adapter.

Core goals:

- deterministic offline execution
- no-lookahead by default (mandatory lag)
- governance boundaries: execution/cost come from policies only
- trace preview and backtest share the same signal compiler (single truth)

## 1) Inputs (SSOT)

- Prices: queried via `DataCatalog` (enforces `available_at <= as_of`).
- Policies (read-only, via bundle):
  - `asof_latency_policy_v1`: `trade_lag_bars_default` (default 1, must be >= 1)
  - `execution_policy_v1`: timing/fill + `allow_short` (v1 MVP executes long-only)
  - `cost_policy_v1`: commission/slippage (bps)
- Strategy: `signal_dsl_v1` (declarative AST)

## 2) Supported DSL Subset (v1)

### AST nodes

- `const`, `var`, `param`, `op` (see `contracts/defs/expression_ast_v1.json`)

### Supported `op` names

Boolean:

- `and`, `or`, `not`

Comparisons:

- `eq`, `gt`, `lt`, `ge`, `le`

Arithmetic:

- `add`, `sub`, `mul`, `div`

Indicators:

- `sma(series, n)`: trailing simple moving average, `min_periods=n`
- `rsi(series, n)`: Wilder RSI using EMA smoothing (alpha=1/n), range ~[0,100]

Signal ops:

- `cross_above(a, b)`: `(a > b) & (a.shift(1) <= b.shift(1))`
- `cross_below(a, b)`: `(a < b) & (a.shift(1) >= b.shift(1))`

Notes:

- All computations are done per-symbol and sorted stably by `(symbol, dt)`.
- Missing values (e.g. early SMA windows) result in `False` for boolean signals.

## 3) No-Lookahead + Lag Semantics (Hard Rule)

The executable entry/exit signals are:

- `entry_lagged = entry_raw.shift(lag_bars)`
- `exit_lagged = exit_raw.shift(lag_bars)`

Where:

- `lag_bars = asof_latency_policy.params.trade_lag_bars_default`
- `lag_bars` must be >= 1

This prevents same-bar lookahead when signals are derived from bar-close information.

Position (v1 long-only) is derived from lagged signals:

- start `position=0`
- if `exit_lagged=true` then `position=0`
- if `entry_lagged=true` then `position=1`

If both happen on the same bar, evaluation order is deterministic: exit first, then entry.

## 4) Execution + Costs (Policy-Only)

- `execution_policy_v1` determines supported timing/fill combinations.
- `cost_policy_v1` determines commission/slippage.
- The DSL must not inline cost/execution policy params (governance red line).

## 5) Strategy Templates (Examples)

### MA Crossover (long-only)

Intermediates:

- `sma_fast = sma(close, fast)`
- `sma_slow = sma(close, slow)`

Signals:

- `entry_raw = cross_above(sma_fast, sma_slow)`
- `exit_raw = cross_below(sma_fast, sma_slow)`

### RSI Mean Reversion (long-only)

Intermediate:

- `rsi = rsi(close, n)`

Signals:

- `entry_raw = rsi < entry_th`
- `exit_raw = rsi > exit_th`

## 6) Evidence Fields

Backtest stats include:

- `dsl_fingerprint`: sha256 of canonical DSL JSON
- `signals_fingerprint`: sha256 of canonical `(symbol,dt,entry_lagged,exit_lagged)` records

These are used to assert trace-preview and backtest consistency.
