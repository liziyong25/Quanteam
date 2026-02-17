# Policies Index (v1)

Policies are frozen governance inputs for Kernel/Compiler/Runner/GateRunner/UI. Strategies/modules must only reference
`policy_id` (or `policy_bundle_id`) and must not override or inline policy content.

Versioning rule: v1 is immutable. Any change must be a new file (v2+) with ADR + regression evidence.

## Assets (v1)

- Execution Policy: `policies/execution_policy_v1.yaml`
  - Docs: `docs/04_policies/execution_policy_v1.md`
- Cost Policy: `policies/cost_policy_v1.yaml`
  - Docs: `docs/04_policies/cost_policy_v1.md`
- As-Of / Latency Policy: `policies/asof_latency_policy_v1.yaml`
  - Docs: `docs/04_policies/asof_latency_policy_v1.md`
- Risk Policy: `policies/risk_policy_v1.yaml`
  - Docs: `docs/04_policies/risk_policy_v1.md`
- Gate Suite: `policies/gate_suite_v1.yaml`
  - Docs: `docs/04_policies/gate_suite_v1.md`
- Gate Suite (Snapshot Integrity v2): `policies/gate_suite_v2_snapshot_integrity.yaml`
  - Adds `data_snapshot_integrity_v1` gate without modifying v1 assets.
- Gate Suite (Holdout Leak Guard v2): `policies/gate_suite_v2_holdout_guard.yaml`
  - Adds `holdout_leak_guard_v1` to prevent second-order holdout leakage into iteration-facing artifacts.
- Gate Suite (Composer): `policies/gate_suite_curve_composer_v1.yaml`
  - Used by Phase-09 curve-level composition runs (adapter `curve_composer_v1`).
- Budget/Stop Policy: `policies/budget_policy_v1.yaml`
  - Docs: `docs/04_policies/budget_policy_v1.md`
- LLM Budget Policy: `policies/llm_budget_policy_v1.yaml`
  - Docs: `docs/04_policies/llm_budget_policy_v1.md`
- Policy Bundle: `policies/policy_bundle_v1.yaml`
  - Docs: `docs/04_policies/policy_bundle_v1.md`
- Policy Bundle (Snapshot Integrity v2): `policies/policy_bundle_v2_snapshot_integrity.yaml`
  - Switches `gate_suite_id` to include snapshot integrity verification.
- Policy Bundle (Holdout Leak Guard v2): `policies/policy_bundle_v2_holdout_guard.yaml`
  - Switches `gate_suite_id` to include holdout leakage guard.
- Policy Bundle (Composer): `policies/policy_bundle_curve_composer_v1.yaml`
  - Composition runs must reference this `policy_bundle_id` (single handle); policies remain read-only.

## Tooling

- Validate a single policy:
  - `python -m quant_eam.policies.validate policies/execution_policy_v1.yaml`
- Validate a bundle (resolves referenced policy_id in `policies/`):
  - `python -m quant_eam.policies.validate policies/policy_bundle_v1.yaml`

## Replay & Anti-Tamper: `policy_lock_v1`

`policies/policy_lock_v1.json` is a **record** of policy ids and file hashes used for replayability and anti-tamper.
It is not a configuration source and must not override policy semantics.

- Generate/update lock:
  - `python -m quant_eam.policies.validate --write-lock policies/`
- When validating a bundle:
  - If `policy_lock_v1.json` exists, validator will verify:
    - referenced policy ids exist in the lock
    - each referenced policy file sha256 matches the lock record

## Validate Directory

To reduce omissions, you can validate all `*_v1.yaml` assets in a directory:

- `python -m quant_eam.policies.validate policies/`
