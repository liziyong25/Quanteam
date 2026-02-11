# Calc Trace Plan v1 (`calc_trace_plan_v1`)

Schema: `contracts/calc_trace_plan_v1.json`

## Purpose

- Producer: blueprint author or tooling (future).
- Consumer: trace runner + UI (future) to generate/visualize demo artifacts.

This is a plan, not execution logic.

## Top-Level Fields (v1)

- `schema_version`: must be `"calc_trace_plan_v1"`
- `extensions`: optional object for forward-compatible metadata (must not override governance/policies)
- `samples[]`: symbols + date range + `max_rows`
- `steps[]`: render steps (each references `variables[]`)
- `assertions[]`: optional assertions (e.g. `lag_enforced`)

## Examples

- OK: `contracts/examples/calc_trace_plan_ok.json`
- BAD: `contracts/examples/calc_trace_plan_bad.json`
