# Risk Policy v1

File: `policies/risk_policy_v1.yaml`

## Purpose

- Producer: governance
- Consumer: Kernel/Runner risk constraints layer (future), UI review

This is a declarative threshold policy. Enforcement is implemented later; v1 only defines the governed surface.

## Key Fields

- `params.max_leverage`: number
- `params.max_positions`: int
- `params.max_turnover`: number
- Optional: `params.max_drawdown`: number (threshold declaration only)
- `extensions` (optional): forward-compatible metadata only

## Forbidden

- Ad-hoc per-strategy risk overrides not represented as a new policy version.

