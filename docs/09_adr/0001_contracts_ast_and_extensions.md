# ADR-0001: Contracts v1 AST Single Truth + `extensions` Forward Compatibility

- Status: Accepted
- Date: 2026-02-09
- Owners: Quant-EAM contributors

## Context

- Contracts are SSOT for cross-module I/O. If Expression AST diverges between Signal DSL and Variable Dictionary, validators and tools will drift and replayability breaks.
- v1 needs to be minimal but evolvable. If v1 schemas are too rigid, we end up "breaking v1" or adding ad-hoc fields outside contracts.
- Governance requires policies to be read-only references by id; forward-compat fields must not become a loophole for overrides.

## Decision

- Define a common Expression AST schema:
  - `contracts/defs/expression_ast_v1.json`
  - Both `signal_dsl_v1` and `variable_dictionary_v1` reference this single definition via `$ref`.
- Add an optional top-level `extensions` object to all v1 contracts to support forward-compatible metadata:
  - `extensions` allows arbitrary key/value.
  - `extensions` must not override governance, policy content, determinism, or inject executable behavior.

## Consequences

### Positive

- Eliminates AST drift risk: one schema defines AST structure and recursion.
- Allows non-breaking additions without forcing v2 immediately.
- Keeps governance boundaries explicit: policies remain referenced by id.

### Negative / Trade-offs

- `extensions` can become a dumping ground if not reviewed. Requires review discipline.
- Some future v2 changes will still require explicit version bump + adapters; `extensions` is not a substitute for real schema evolution.

## Alternatives Considered

- Duplicate AST definitions in each schema:
  - Rejected: guarantees drift over time.
- No `extensions` field in v1:
  - Rejected: encourages ad-hoc non-contract fields and "hidden schema" outside SSOT.

## Compatibility / Migration

- v1 examples remain valid; `extensions` is optional.
- Future v2 can add/rename fields while keeping v1 replayable via adapters.

## References

- `docs/03_contracts/contracts_index.md`
- `contracts/defs/expression_ast_v1.json`
- `contracts/signal_dsl_v1.json`
- `contracts/variable_dictionary_v1.json`

