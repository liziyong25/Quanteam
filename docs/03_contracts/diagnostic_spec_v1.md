# Diagnostic Spec v1

## Purpose

`diagnostic_spec_v1` defines a deterministic diagnostics plan attached to one run.
It is the contract boundary between dossier evidence and promotion candidate generation.

Producer: diagnostics pipeline or diagnostics agent  
Consumers: diagnostics runner, UI run diagnostics view, promotion candidate builder

## Key Fields

- `schema_version`: must be `"diagnostic_spec_v1"`.
- `diagnostic_id`: stable diagnostics id within one run.
- `run_id`: source run id.
- `title` / `objective`: human-readable intent.
- `artifacts`: optional references to source evidence paths.
- `checks[]`:
  - `check_id`
  - `metric_key`
  - `operator` in `{lt, le, gt, ge, eq, ne}`
  - `threshold`
  - `severity` in `{info, warn, error}`

## Determinism Notes

- The contract is data-only; no executable script payload is allowed.
- The same input contract and same dossier evidence must produce the same diagnostics outputs.
- Promotion logic must reference evidence paths, not free-text arbitration.

## Examples

- OK: `contracts/examples/diagnostic_spec_ok.json`
- BAD: `contracts/examples/diagnostic_spec_bad.json`
