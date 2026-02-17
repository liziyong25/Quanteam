# WV-045..WV-050 Kernel Bundle Spec v1

## 1. Scope

This document defines the skeleton execution-contract bundle for:

- WV-045: contracts module (schemas + validation)
- WV-046: compiler (`Blueprint -> RunSpec`, budget injection, compliance checks)
- WV-047: runner (`RunSpec -> Dossier`)
- WV-048: gate_runner (`RunSpec + Dossier -> GateResults`)
- WV-049: holdout_vault isolation
- WV-050: dossier_builder append-only report generation

The bundle is docs-only for skeleton closure. It does not modify `contracts/**`
or `policies/**`.

## 2. Dependency Freeze (G289/WV-044)

- `WV-044` is the prerequisite deterministic-kernel boundary and is treated as frozen
  input for this bundle.
- Frozen object flow: `Blueprint -> RunSpec -> Dossier -> GateResults`.
- Frozen identity anchors propagated across stages:
  - `run_id`
  - `blueprint_hash`
  - `policy_bundle_id`
  - `data_snapshot_id`

## 3. WV-045 Contracts + Validation Entrypoints

Schema references:

- `contracts/blueprint_schema_v1.json`
- `contracts/run_spec_schema_v1.json`
- `contracts/dossier_schema_v1.json`
- `contracts/gate_results_schema_v2.json`

Required validation entrypoints:

- `validate_blueprint(payload)`
- `validate_runspec(payload)`
- `validate_dossier(payload)`
- `validate_gate_results(payload)`

Validation rules:

- Discriminator/version field must be present and non-empty.
- Required IDs must be present (`run_id`, `policy_bundle_id`, snapshot IDs).
- Missing required fields fail fast without coercion.
- Validation errors are deterministic in field-path order.

Reusable fixture index:

- `docs/05_data_plane/wv045_wv050_kernel_bundle_fixtures_v1.json`

## 4. WV-046 Compiler Contract (Blueprint -> RunSpec)

- Compiler input must pass `validate_blueprint` before compilation.
- Compiler output must pass `validate_runspec` before writeback.
- Compiler must inject budget envelope fields into RunSpec:
  - `budget.capital_limit`
  - `budget.max_drawdown_limit`
  - `budget.cost_limit`
- Compiler must emit compliance metadata:
  - `compliance.policy_bundle_id`
  - `compliance.checks[]`
  - `compliance.rejection_reason` (required on fail)
- Compilation fails when required compliance anchors are missing.

## 5. WV-047 Runner Contract (RunSpec -> Dossier)

- Runner consumes only validated RunSpec payloads.
- Runner emits Dossier artifacts and `dossier_manifest` as append-only outputs.
- Runner must preserve the frozen identity anchors from Section 2.
- Runner output must pass `validate_dossier`.

## 6. WV-048 Gate Runner Contract (Gates -> GateResults)

- Gate runner consumes:
  - validated RunSpec
  - append-only Dossier evidence references
- Gate runner outputs GateResults payload and must pass `validate_gate_results`.
- Gate checks must execute in deterministic order and include evidence refs for each
  pass/fail decision.

## 7. WV-049 Holdout Vault Isolation Contract

- Holdout artifacts are stored under isolated holdout-only paths.
- Generation/tuning loops cannot read raw holdout internals.
- Exposed output is restricted to `pass/fail + minimal summary`.
- Non-approved holdout access attempts fail with explicit denial reason.

## 8. WV-050 Dossier Builder Append-Only Contract

- Dossier builder produces chart/table/report artifacts as write-once records.
- Retry/regeneration writes new attempt/version artifacts and never overwrites old
  files.
- Append-only keys are `(run_id, attempt, artifact_kind, artifact_id)`.
- Cleanup routines must not mutate historical artifacts.

## 9. Risk Control Mapping

- G289 interface drift risk: controlled by the dependency freeze in Section 2.
- Schema-validator mismatch risk: controlled by shared entrypoints in Section 3.
- Compliance coverage gap risk: controlled by Section 4 required compliance fields.
- Holdout leak risk: controlled by Section 7 isolation and summary-only output.
- Append-only bypass risk: controlled by Section 8 write-once rules.
