# Phase-27: Protocol Hardening v1

## Goal

Seal four "non-blocking but will explode later" protocol risks:

1. RunSpec/Segments and GateResults schema coverage gray area.
2. Second-order holdout leakage channels.
3. Risk gate uses evidence aligned with backtest intermediate artifacts.
4. Ruff gate scope shrink illusion (add explicit coverage plan + gate).

## Scope

In-scope:

- New contracts: `run_spec_v2`, `gate_results_v2` (+ examples/tests).
- New gate: `holdout_leak_guard_v1` + new gate suite/bundle file.
- Backtest/Runner writes risk evidence artifacts; risk gate consumes them.
- Lint scope plan + check script + CI-local step.

Out-of-scope:

- Changing existing v1 schema/policy file contents.
- Adding network IO to tests.

## Deliverables

- Contracts:
  - `contracts/run_spec_schema_v2.json`
  - `contracts/gate_results_schema_v2.json`
- Gates/Policies:
  - `holdout_leak_guard_v1`
  - `policies/gate_suite_v2_holdout_guard.yaml`
  - `policies/policy_bundle_v2_holdout_guard.yaml`
- Risk evidence artifacts:
  - `positions.csv`, `turnover.csv`, `exposure.json` written to dossier
  - `risk_policy_compliance_v1` consumes those artifacts
- Lint gate:
  - `docs/07_runbooks/lint_coverage_plan.md`
  - `scripts/check_lint_scope.py`
  - `scripts/ci_local.sh` runs lint scope check before ruff

## Acceptance

- `pytest -q` passes (container).
- `python3 scripts/check_docs_tree.py` passes.

## Execution Log

- Start Date: 2026-02-11 (Asia/Taipei)
- End Date: 2026-02-11 (Asia/Taipei)
- Commit: unknown (not recorded in this patch log)

