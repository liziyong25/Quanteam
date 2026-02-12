# Phase-17: Data Snapshot Integrity Gate v1 + Provenance Linkage

## Goal

- Add a deterministic gate `data_snapshot_integrity_v1` that validates snapshot contracts + anti-tamper sha256 checks.
- Add v2 gate suite + policy bundle to enable the new gate without modifying any `*_v1.yaml`.
- Add UI read-only links from Job/Run pages to Snapshot detail pages.

## Scope

- In scope: `src/quant_eam/gates/**`, `src/quant_eam/gaterunner/**`, `src/quant_eam/snapshots/**`, `policies/**` (new v2 files),
  UI templates/routes, docs, tests.
- Out of scope: changes to contracts v1 semantics, runner/compiler behavior, any write operations on `/data` in UI.

## Deliverables

- Gate implementation: `src/quant_eam/gates/data_snapshot_integrity.py`
- Gate registry entry: `src/quant_eam/gates/registry.py`
- v2 policy assets:
  - `policies/gate_suite_v2_snapshot_integrity.yaml`
  - `policies/policy_bundle_v2_snapshot_integrity.yaml`
- Docs:
  - `docs/08_gates/data_snapshot_integrity_v1.md`
  - (this file)
- Tests:
  - e2e PASS: ingest -> compile -> run -> gates includes snapshot integrity PASS
  - tamper FAIL: mutate `ohlcv_1d.csv` after snapshot write -> gate must FAIL with sha mismatch evidence

## Execution Log

- Start Date (Asia/Taipei): 2026-02-10
- End Date (Asia/Taipei): 2026-02-10
- Commit: unknown
- Notes:
  - Added a new deterministic gate to validate snapshot evidence chain (contracts + sha256).
  - Added read-only provenance links in UI from jobs/runs to snapshots.

