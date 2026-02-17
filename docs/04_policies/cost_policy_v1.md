# Cost Policy v1

File: `policies/cost_policy_v1.yaml`

## Purpose

- Producer: governance (repo policy assets)
- Consumer: Kernel/Runner cost adapter (future), UI review (read-only)

Strategies must not inline cost models. They reference policy ids only.

## Key Fields

- `policy_id`, `policy_version`
- `params.commission_bps`, `params.slippage_bps`: numbers
- Optional: `tax_bps`, `min_fee`, `currency`
- `extensions` (optional): forward-compatible metadata only

## Forbidden

- Strategy/DSL setting its own commission/slippage numbers.
- Editing v1 content; use v2+.

