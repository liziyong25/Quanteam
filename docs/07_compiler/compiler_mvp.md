# Compiler MVP: Blueprint -> RunSpec (v1)

## Purpose

- Input: Blueprint v1 (includes Signal DSL v1)
- Output: RunSpec v1 (consumed by Runner Phase-04)

The compiler is deterministic and does not mutate governance inputs.

## Policy Boundary (Non-negotiable)

- Blueprint must reference `policy_bundle_id`.
- Compiler must not "swap" or override policy bundle at compile time.
- If `blueprint.policy_bundle_id` does not match the provided `policy_bundle_v1.yaml` id, compilation fails.

## as_of Semantics

Data availability semantics are fixed by policy:

- `asof_latency_policy_v1.params.asof_rule == "available_at<=as_of"`

Compiler generates RunSpec segments with `as_of`:

- If Blueprint segment already has `as_of`, it is used.
- Otherwise, default `as_of` is `end_dateT23:59:59+08:00` (Asia/Taipei fixed offset).

Optional check:

- `--check-availability` queries DataCatalog and fails compilation if 0 rows are available under the computed `as_of`.

## Adapter Selection (MVP)

Phase-05 MVP supports:

- `adapter_id = "vectorbt_signal_v1"` (matches Phase-04 runner/backtest adapter id)

## CLI

```bash
python -m quant_eam.compiler.compile \
  --blueprint contracts/examples/blueprint_buyhold_demo_ok.json \
  --snapshot-id demo_snap_001 \
  --out /tmp/runspec_demo.json \
  --policy-bundle policies/policy_bundle_v1.yaml
```

Then run:

```bash
python -m quant_eam.runner.run \
  --runspec /tmp/runspec_demo.json \
  --policy-bundle policies/policy_bundle_v1.yaml
```

