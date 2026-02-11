# RunSpec v1 (`run_spec_v1`)

Schema: `contracts/run_spec_schema_v1.json`

## Purpose

- Producer: compiler (future) from a Blueprint + policies + data catalog snapshot.
- Consumer: kernel/runner (future).

RunSpec is declarative and must be replayable. Any PASS/FAIL/registry action must reference dossier artifacts produced by the run.

## Top-Level Fields (v1)

- `schema_version`: must be `"run_spec_v1"`
- `extensions`: optional object for forward-compatible metadata (must not override governance/policies)
- `blueprint_ref`: `{blueprint_id, blueprint_hash}`
- `policy_bundle_id`: policy bundle reference (read-only)
- `data_snapshot_id`: immutable data snapshot id
- `segments.train/test/holdout`: each `{start,end,as_of}`
- `adapter.adapter_id`: execution adapter selector (e.g. `vectorbt_signal_v1`)
- `output_spec`:
  - `write_dossier=true` (v1 enforces)
  - `artifacts`: logical name -> output path (used by dossier manifest)

## As-Of Semantics (v1)

`segments.*.as_of` is the timestamp used for data availability semantics. The runner must not access data newer than `as_of`.

## Examples

- OK: `contracts/examples/run_spec_ok.json`
- BAD: `contracts/examples/run_spec_bad.json` (missing `segments.holdout` fails)
- BAD: `contracts/examples/run_spec_missing_as_of_bad.json` (missing `segments.holdout.as_of` fails)
