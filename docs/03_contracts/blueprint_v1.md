# Blueprint v1 (`blueprint_v1`)

Schema: `contracts/blueprint_schema_v1.json`

## Purpose

- Producer: human/agent (proposal), reviewed by human.
- Consumer: compiler (future), which produces a deterministic `RunSpec`.

Blueprint is declarative and statically analyzable. It must reference policies by id only.

## Top-Level Fields (v1)

- `schema_version`: must be `"blueprint_v1"` (discriminator)
- `extensions`: optional object for forward-compatible metadata (must not override governance/policies)
- `blueprint_id`: stable id for review + hashing
- `title`: human-readable title
- `universe`: `{asset_pack, symbols, timezone, calendar}`
- `bar_spec`: `{frequency}`
- `policy_bundle_id`: policy reference (read-only id)
- `data_requirements[]`: dataset/fields/frequency/adjustment/asof_rule
- `strategy_spec`: `signal_dsl_v1` object (DSL)
- `evaluation_protocol`:
  - `segments.train/test/holdout`: each has `{start, end, as_of?}`
  - `purge.bars`, `embargo.bars`: leakage controls
  - `gate_suite_id`: gate suite reference (read-only id)
- `report_spec`: `{plots, tables, trace}` (trace enables demo artifacts)

## Key Semantics

- Policies: `policy_bundle_id` is a reference only. Blueprint cannot inline/override policy behavior.
- Holdout: blueprint declares holdout segment; holdout output is restricted by protocol (pass/fail + minimal summary).
- This contract does not encode "strategy is good/bad" logic. That is gate + dossier territory.

## Examples

- OK: `contracts/examples/blueprint_ok.json`
- BAD: `contracts/examples/blueprint_bad.json`
