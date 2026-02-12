# Gate Spec v1

## Purpose

`gate_spec_v1` is a promotion-candidate contract generated from diagnostics evidence.
It does not replace GateRunner arbitration directly; it provides an auditable candidate
set of gates that can be reviewed and promoted through governed workflows.

Producer: diagnostics promotion chain  
Consumers: gate-spec review UI, governance workflow, future gate suite materialization

## Key Fields

- `schema_version`: must be `"gate_spec_v1"`.
- `gate_spec_id`: stable candidate id.
- `source_run_id`: source run id.
- `source_diagnostic_id`: source diagnostics id.
- `candidate_gates[]`:
  - `gate_id`
  - `expression` (declarative expression string)
  - `severity` in `{warn, fail}`
  - `evidence_refs[]` (required, append-only evidence pointers)
  - optional `threshold`

## Determinism Notes

- Candidate gates must cite evidence refs from dossier/diagnostics artifacts.
- The contract does not include executable policy override payloads.
- PASS/FAIL remains decided by deterministic GateRunner with policy bundles.

## Examples

- OK: `contracts/examples/gate_spec_ok.json`
- BAD: `contracts/examples/gate_spec_bad.json`
