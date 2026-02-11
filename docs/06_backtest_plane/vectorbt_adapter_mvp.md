# Vectorbt Adapter MVP (`vectorbt_signal_v1`)

Adapter id: `vectorbt_signal_v1`

This phase provides an adapter surface compatible with the v1 RunSpec `adapter.adapter_id`.
If `vectorbt` is installed, it may be used internally in later phases; for MVP we keep a deterministic minimal engine as
the reference behavior.

## Inputs

- Prices from DataCatalog (already `available_at <= as_of` filtered)
- Policies (read-only):
  - `execution_policy_v1` for timing/fill price
  - `cost_policy_v1` for commission/slippage
  - `asof_latency_policy_v1` for `trade_lag_bars_default`

## Strategy MVP: `buy_and_hold_mvp`

- Entry: first available bar
- Exit: end of segment

## No Lookahead: mandatory lag

Signals are shifted forward by `lag_bars`:

- `lag_bars = asof_latency_policy.params.trade_lag_bars_default` (default 1)
- Rationale: safe default to prevent same-bar lookahead when signals are computed from bar-close data.

## Costs and execution (policy-only)

- Commission and slippage must come from `cost_policy_v1` (bps -> fraction).
- Execution timing must come from `execution_policy_v1`.
- Strategy must not override any cost/execution parameters.

