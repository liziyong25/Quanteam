# ADR-0002: GateRunner v1, GateResults Contract, and Holdout Minimal Output

## Context

We need a deterministic arbitration layer that:

- consumes append-only dossier artifacts (SSOT evidence)
- consumes read-only policies (governance input)
- emits a structured, contract-validated gate output for UI/promotion logic

Holdout evaluation must be strictly isolated to avoid leakage into iterative loops.

## Decision

1) Introduce a versioned GateResults contract:

- `contracts/gate_results_schema_v1.json` (`schema_version="gate_results_v1"`)
- Output path fixed to `<dossier_dir>/gate_results.json`

2) Implement GateRunner v1:

- CLI: `python -m quant_eam.gaterunner.run --dossier <dir> --policy-bundle <path>`
- Loads gate suite via `gate_suite_id` from the policy bundle
- Writes `gate_results.json` append-only (no rewrite if already present)

3) Enforce holdout output restriction via HoldoutVault:

- Holdout evaluation returns only `pass/fail + minimal summary (+ optional minimal metrics)`
- GateRunner must never write holdout curves/trades into the dossier

## Consequences

Pros:

- Gate outputs become a contract-defined, replayable artifact.
- UI/promotion can use `gate_results.json` + dossier artifacts as the only evidence chain.
- Holdout leakage is structurally prevented in the MVP.

Cons / limitations:

- v1 uses a minimal gate set and conservative defaults.
- Gate suite policy can evolve to add gates, but v1 behavior must remain replayable.

## Alternatives Considered

- Store gate results only as logs: rejected (not replayable, not contract-validated).
- Store holdout curves/trades for debugging: rejected (violates holdout isolation).

## Migration / Future Work

- Add v2 gate suite assets to version gate definitions without breaking v1 replay.
- Add explicit gate result `status` semantics (pass/fail/skipped) across all gates.
- Consider adding a dedicated contract page under `docs/03_contracts/` for gate_results v2+.

## References

- Governance: `docs/01_governance.md`
- Protocols: `docs/02_protocols.md` (Dossier protocol, Holdout protocol)
- Gates docs: `docs/08_gates/gates_index.md`

