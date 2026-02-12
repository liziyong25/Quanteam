# Contracts Index (v1)

Contracts are versioned schemas for cross-module I/O. They define structure only; they do not decide strategy validity.

All contracts are:

- Versioned by filename (`*_v1.json`) and by discriminator field (`schema_version` / `dsl_version` const).
- Validated via `python -m quant_eam.contracts.validate <json_path>`.
- Policies are **read-only references** by id (no inline/override).
- Any PASS/FAIL/Registry write must reference dossier artifacts (evidence chain).

## Forward Compatibility: `extensions`

Each v1 contract schema includes an optional top-level `extensions` object:

- Purpose: forward-compatible space for experiments and non-breaking metadata.
- Hard boundary: `extensions` must **not** be used to override governance, policies, determinism rules, or to smuggle executable behavior.

## Single Truth: Expression AST

Expression AST must have a single source of truth:

- Common AST schema: `contracts/defs/expression_ast_v1.json`
- `signal_dsl_v1` expressions and `variable_dictionary_v1` compute AST must reference the same AST definition (via `$ref`).
- Validator resolves `$ref` from the local schema registry (no network IO).

## Version Discriminators (No Silent Mismatch)

- Every schema requires `schema_version` or `dsl_version` and constrains it to the exact v1 value.
- Unknown version values are invalid. Do not "accept and guess".

## Schemas (v1)

- Blueprint: `contracts/blueprint_schema_v1.json`
  - Docs: `docs/03_contracts/blueprint_v1.md`
  - Examples: `contracts/examples/blueprint_ok.json`, `contracts/examples/blueprint_bad.json`
- Signal DSL: `contracts/signal_dsl_v1.json`
  - Docs: `docs/03_contracts/signal_dsl_v1.md`
  - Examples: `contracts/examples/signal_dsl_ok.json`, `contracts/examples/signal_dsl_bad.json` (and other `*_bad.json`)
- Variable Dictionary: `contracts/variable_dictionary_v1.json`
  - Docs: `docs/03_contracts/variable_dictionary_v1.md`
  - Examples: `contracts/examples/variable_dictionary_ok.json`, `contracts/examples/variable_dictionary_bad.json`
- Calc Trace Plan: `contracts/calc_trace_plan_v1.json`
  - Docs: `docs/03_contracts/calc_trace_plan_v1.md`
  - Examples: `contracts/examples/calc_trace_plan_ok.json`, `contracts/examples/calc_trace_plan_bad.json`
- RunSpec: `contracts/run_spec_schema_v1.json`
  - Docs: `docs/03_contracts/run_spec_v1.md`
  - Examples: `contracts/examples/run_spec_ok.json`, `contracts/examples/run_spec_bad.json` (and other `*_bad.json`)
- RunSpec v2 (segments.list explicit): `contracts/run_spec_schema_v2.json`
  - Docs: `docs/03_contracts/run_spec_v2.md`
  - Examples: `contracts/examples/run_spec_v2_ok.json`, `contracts/examples/run_spec_v2_missing_list_bad.json`
- Dossier Manifest: `contracts/dossier_schema_v1.json`
  - Docs: `docs/03_contracts/dossier_v1.md`
  - Examples: `contracts/examples/dossier_ok.json`, `contracts/examples/dossier_bad.json` (and other `*_bad.json`)
- Gate Results: `contracts/gate_results_schema_v1.json`
  - Docs: `docs/08_gates/gates_index.md` (gate contract + semantics)
  - Producer: GateRunner
  - Consumer: UI / promotion logic (future)
- Gate Results v2 (segment_results explicit): `contracts/gate_results_schema_v2.json`
  - Docs: `docs/03_contracts/gate_results_v2.md`
  - Producer: GateRunner
  - Consumer: UI / promotion logic (future)
- Trial Event (Registry TrialLog): `contracts/trial_event_schema_v1.json`
  - Docs: `docs/09_registry/trial_log_v1.md`
  - Producer: Registry (record-trial)
  - Consumer: UI / auditing / registry pipelines
- Experience Card: `contracts/experience_card_schema_v1.json`
  - Docs: `docs/09_registry/experience_cards_v1.md`
  - Producer: Registry (create-card)
  - Consumer: UI / composer (future)
- Diagnostic Spec: `contracts/diagnostic_spec_v1.json`
  - Docs: `docs/03_contracts/diagnostic_spec_v1.md`
  - Examples: `contracts/examples/diagnostic_spec_ok.json`, `contracts/examples/diagnostic_spec_bad.json`
- Gate Spec: `contracts/gate_spec_v1.json`
  - Docs: `docs/03_contracts/gate_spec_v1.md`
  - Examples: `contracts/examples/gate_spec_ok.json`, `contracts/examples/gate_spec_bad.json`

## Validator

CLI:

```bash
python -m quant_eam.contracts.validate contracts/examples/blueprint_ok.json
python -m quant_eam.contracts.validate --examples contracts/examples
```

Selection:

- If JSON has `schema_version`, choose schema by `schema_version`.
- Else if JSON has `dsl_version`, choose schema by `dsl_version`.
- If both are missing: usage error (exit=1). Use `--schema` to force a schema.
