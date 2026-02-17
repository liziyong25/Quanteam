# Execution Policy v1

File: `policies/execution_policy_v1.yaml`

## Purpose

- Producer: governance (repo policy assets)
- Consumer: Kernel/Runner (future), Compiler adapter selection (future), UI display (read-only)

This policy declares execution mechanics (timing, fill price). It is not a backtest script and does not decide validity.

## Key Fields

- `policy_id`: stable identifier referenced by bundle and RunSpec/Dossier
- `policy_version`: must be `"v1"`
- `params.order_timing`: `next_open | close | next_close`
- `params.fill_price` (optional): `open | close | vwap`
- `params.allow_short`: boolean
- `params.lot_size` / `params.rounding` (optional): integer and rounding mode
- `extensions` (optional): forward-compatible metadata only (must not override governance)

## Forbidden

- Inlining or overriding execution behavior inside strategies/DSL.
- Mutating v1 files. Any change requires v2+ file + ADR.

