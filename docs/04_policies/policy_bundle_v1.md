# Policy Bundle v1

File: `policies/policy_bundle_v1.yaml`

## Purpose

- Producer: governance
- Consumer: Blueprint/RunSpec (references `policy_bundle_id`), Kernel/Runner/GateRunner/UI (future)

Bundle is the single handle referenced by strategies/modules. It composes multiple frozen policies by id.

## Key Fields

- `policy_bundle_id`: stable bundle identifier
- `policy_version`: must be `"v1"`
- `execution_policy_id`, `cost_policy_id`, `asof_latency_policy_id`, `risk_policy_id`, `gate_suite_id`: string references
- `extensions` (optional): forward-compatible metadata only

## Hard Rules

- Bundle must reference existing policy ids in `policies/`.
- Bundle must not inline or override params; it references ids only.
- Changes require v2+ bundle file + ADR + regression evidence.

