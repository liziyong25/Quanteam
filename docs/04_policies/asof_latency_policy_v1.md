# As-Of / Latency Policy v1

File: `policies/asof_latency_policy_v1.yaml`

## Purpose

- Producer: governance
- Consumer: Kernel data adapter / Runner (future), Compiler (future), UI review

Defines the as-of availability rule and default latency/lag values to prevent lookahead.

## Key Fields

- `params.asof_rule`: fixed semantics `"available_at<=as_of"`
- `params.default_latency_seconds`: integer
- Optional: `bar_close_to_signal_seconds`, `trade_lag_bars_default` (default 1)
- `extensions` (optional): forward-compatible metadata only

## Forbidden

- Any module changing as-of semantics without policy versioning + ADR.

