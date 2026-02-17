# Signal DSL v1 (`signal_dsl_v1`)

Schema: `contracts/signal_dsl_v1.json`

## Purpose

- Producer: blueprint author / agent proposal.
- Consumer: compiler + adapter (e.g. `vectorbt_signal_v1`) and trace/runner (future).

This DSL is declarative. It describes signals via AST expressions.

## Top-Level Fields (v1)

- `dsl_version`: must be `"signal_dsl_v1"` (discriminator)
- `extensions`: optional object for forward-compatible metadata (must not override governance/policies)
- `signals.entry` / `signals.exit`: expression keys (strings)
- `expressions`: `{name -> AST}` map
- `execution.order_timing`: `"next_open" | "next_close" | "open" | "close"`
- `execution.cost_model`: must be a policy reference (`ref_policy=true`)
- `constraints`: optional (e.g. `max_turnover`)

## AST Node Types (v1)

- `{"type":"var","var_id":"..."}`
- `{"type":"const","value":...}`
- `{"type":"param","param_id":"..."}`
- `{"type":"op","op":"...","args":[...]}`

AST single truth:

- AST schema is shared via `contracts/defs/expression_ast_v1.json` and referenced by `$ref`.

## Policy Boundary (Hard Constraint)

Cost model cannot be inlined. Schema enforces `execution.cost_model.ref_policy == true`.

## Examples

- OK: `contracts/examples/signal_dsl_ok.json`
- BAD: `contracts/examples/signal_dsl_bad.json`
- BAD (version mismatch): `contracts/examples/signal_dsl_version_bad.json`
