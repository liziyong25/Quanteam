# RunSpec v2

## Purpose

`run_spec_v2` is the **Compiler output** contract consumed by the **Runner**. It is declarative and must be replayable.

Producer: `quant_eam.compiler`  
Consumer: `quant_eam.runner` / `quant_eam.gaterunner` / UI (read-only)

Non-goals:

- It does not decide strategy validity.
- It must not inline/override policies. Policies are read-only references by `policy_bundle_id`.

## Key Fields

- `schema_version`: must be `"run_spec_v2"`.
- `policy_bundle_id`: read-only reference (must match the bundle used by Runner).
- `data_snapshot_id`: immutable snapshot id for replay.
- `segments`:
  - `segments.list` (required): canonical segment list, stable order.
  - Each segment item must include:
    - `segment_id`, `kind` (`train|test|holdout`), `start`, `end`, `as_of`
    - `holdout` (explicit boolean)
    - `purge_days` / `embargo_days` (explicit results after applying the evaluation protocol rules)
  - Legacy anchors `segments.train/test/holdout` may exist for backward compatibility but **must not override** the canonical `segments.list`.
- `adapter.adapter_id`: must match a registered Runner adapter id (e.g. `vectorbt_signal_v1`).
- `output_spec.artifacts`: logical name -> relative path (for `dossier_manifest.json`).

## Examples

- OK: `contracts/examples/run_spec_v2_ok.json`
- BAD: `contracts/examples/run_spec_v2_missing_list_bad.json`

