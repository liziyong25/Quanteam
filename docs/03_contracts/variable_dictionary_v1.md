# Variable Dictionary v1 (`variable_dictionary_v1`)

Schema: `contracts/variable_dictionary_v1.json`

## Purpose

- Producer: compiler (future) or a blueprint-authoring tool.
- Consumer: adapters/runners/diagnostics (future).

This contract defines a variable DAG and alignment rules. It does not declare PASS/FAIL.

## Top-Level Fields (v1)

- `schema_version`: must be `"variable_dictionary_v1"`
- `extensions`: optional object for forward-compatible metadata (must not override governance/policies)
- `variables[]`: each variable defines one series

## Variable Fields (v1)

- `var_id`: stable id
- `kind`: `field | feature | signal`
- `dtype`: logical dtype
- `source` (required when `kind=field`): `{dataset_id, field, adjustment?, frequency?, asof_rule?}`
- `compute.ast` (required when `kind!=field`): declarative AST (shared via `contracts/defs/expression_ast_v1.json`)
- `alignment.lag_bars`:
  - required for all variables
  - for `kind=signal`, schema enforces `lag_bars >= 1` to avoid same-bar lookahead
- `missing_policy.mode`: how to handle missing values

## Examples

- OK: `contracts/examples/variable_dictionary_ok.json`
- BAD: `contracts/examples/variable_dictionary_bad.json` (signal with `lag_bars=0` fails)
