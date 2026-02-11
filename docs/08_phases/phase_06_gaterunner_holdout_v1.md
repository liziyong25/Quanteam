# Phase-06: GateRunner v1 + HoldoutVault v1

## Goal

- Add a deterministic GateRunner that executes a gate suite (from policies) against a dossier.
- Produce append-only `gate_results.json` validated by a contracts schema (`gate_results_v1`).
- Enforce holdout isolation: holdout output restricted to pass/fail + minimal summary only.

## Scope

In scope:

- Gate results contract: `contracts/gate_results_schema_v1.json`
- GateRunner CLI: `python -m quant_eam.gaterunner.run`
- Minimal gates v1 (no-lookahead, lag stress, cost stress, holdout minimal)
- HoldoutVault minimal implementation (no holdout curve/trades written)
- Offline tests (tmp_path + env)
- Docs under `docs/08_gates/`

Out of scope:

- Registry writes / promotion workflow
- UI
- Agents/LLM

## Plan

1) Define `gate_results_v1` as a contract schema and update validator dispatch.
2) Implement GateRunner to read dossier + policy bundle, load gate suite, run gates, and write `gate_results.json` append-only.
3) Implement HoldoutVault restricted output and a holdout gate.
4) Add tests:
   - e2e compile -> run -> gates -> contract validate
   - append-only noop behavior
   - holdout output restriction
   - policy read-only (stress gates must not modify policy files)
5) Add docs and update docs tree check.

## Deliverables

- `contracts/gate_results_schema_v1.json`
- `src/quant_eam/gaterunner/run.py`
- `src/quant_eam/gates/*`
- `src/quant_eam/holdout/vault.py`
- `tests/test_gaterunner_e2e.py`
- `docs/08_gates/*`

## Acceptance

- `pytest -q` passes (offline)
- GateRunner writes `gate_results.json` that validates against `gate_results_v1`
- Running GateRunner twice does not rewrite gate results (append-only noop)
- Holdout evaluation produces only minimal summary (no holdout artifacts written into dossier)

## Execution Log

- Start Date (Asia/Taipei): 2026-02-10
- End Date (Asia/Taipei): 2026-02-10
- Commit: unknown (repo has no git metadata or HEAD not available)

Notes:

- Added `gate_results_v1` contract + validator dispatch.
- Implemented GateRunner + minimal gate registry and HoldoutVault.
- Ensured deterministic output (no timestamps in gate results) and append-only semantics.
- ADR: `docs/09_adr/0002_gaterunner_gate_results_and_holdout_v1.md`
