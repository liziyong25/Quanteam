# Gate Suite v1

File: `policies/gate_suite_v1.yaml`

## Purpose

- Producer: governance
- Consumer: GateRunner, Kernel (future), UI review

Gate suite declares which gates to run and enforces holdout output constraints.

## Key Fields

- `params.gates`: list of `{gate_id, gate_version, params}`
  - Gate algorithms are implemented in `src/quant_eam/gates/` and executed by `python -m quant_eam.gaterunner.run`.
- `params.holdout_policy.output`: must be `"pass_fail_minimal_summary"`
- `extensions` (optional): forward-compatible metadata only

## Forbidden

- Gate suite leaking holdout internals (curves/trades) into iterative loops.
- PASS/FAIL without dossier artifacts references (enforced later by Kernel/Gates).
