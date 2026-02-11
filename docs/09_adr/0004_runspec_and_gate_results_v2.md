# ADR 0004: RunSpec v2 + GateResults v2 (Segments + Holdout Boundaries)

## Context

We already execute multi-segment evaluation (e.g. `segments.list`) and produce per-segment gate outputs, but the v1 schemas do not explicitly cover these structures.

This creates two failure modes:

1. Schema drift: segment fields exist in practice but are "grey area" in contracts.
2. Holdout leakage risk: segment/holdout-related output may accidentally flow into non-contract artifacts where it can be iterated upon.

## Decision

1. Add `run_spec_v2`:
   - Requires `segments.list` (canonical segments list).
   - Each segment item explicitly includes `holdout`, `purge_days`, `embargo_days`.
   - Legacy anchors (`segments.train/test/holdout`) may remain for backward compatibility but must not override `segments.list`.
2. Add `gate_results_v2`:
   - Adds explicit `segment_results[]` (no longer hiding under `extensions`).
   - Keeps holdout output restricted to minimal summary (`holdout_summary`).
3. Update compiler/gaterunner to **default** to v2 outputs, while validator supports v1 and v2 for replay.

## Consequences

- Positive:
  - Contracts now match real I/O; segment semantics are enforceable.
  - UI/Registry can rely on stable structures for segment-level evidence.
- Negative:
  - Some integrations might assume v1 `schema_version`; they must accept v2 discriminators.

## Alternatives Considered

- Keep v1 schemas permissive via `additionalProperties` only:
  - Rejected: does not eliminate the grey area, and invites silent drift.

## Migration

- Validator supports both v1 and v2.
- Producers default to v2.
- Consumers should treat v1/v2 as equivalent where possible, using:
  - `segments.list` when present (else fallback to anchors).
  - `segment_results` when present (else fallback to legacy `extensions.segment_results`).

## References

- `contracts/run_spec_schema_v1.json`, `contracts/run_spec_schema_v2.json`
- `contracts/gate_results_schema_v1.json`, `contracts/gate_results_schema_v2.json`
- `docs/01_governance.md`, `docs/02_protocols.md`

