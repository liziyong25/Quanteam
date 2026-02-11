# Risk Constraints v1

Phase: 22

## Purpose

Make `risk_policy_v1` enforceable in a deterministic way, and produce reviewable evidence in the dossier.

Key ideas:

- Governance thresholds live in `policies/risk_policy_v1.yaml` (read-only).
- Enforcement outcome is arbitrated by **Gate + Dossier** (PASS/FAIL with evidence), not by ad-hoc logs.
- Evidence is written as `risk_report.json` (append-only: new file added to the dossier).

## Evidence: `risk_report.json`

Produced by gate `risk_policy_compliance_v1` (v1).

Fields (MVP):

- `schema_version`: `risk_report_v1`
- `risk_policy_id`
- `policy_params`: max_leverage/max_positions/max_turnover/(optional max_drawdown)
- `series`: `dt[]`, `leverage[]`, `positions_count[]`, `turnover[]`
- `max_observed`
- `violation_count_by_rule`

Computation (deterministic):

- Uses dossier artifacts:
  - `curve.csv` (equity by dt)
  - `trades.csv` (entry/exit + qty)
- Uses DataCatalog close prices for the test segment (as_of enforced: `available_at <= as_of`).

## Semantics (v1)

- If observed risk exceeds policy limits:
  - Gate result is **FAIL** (not INVALID).
- INVALID is reserved for missing evidence inputs (e.g. missing `curve.csv`) or inability to compute (e.g. no data).
- `execution_policy.allow_short=false` is enforced as a hard constraint:
  - any detected short exposure causes FAIL.

## Notes

- This phase computes risk from realized/backtested positions inferred from `(curve,trades)` + DataCatalog prices.
- If future phases add an execution-side clamp/scale-down, the same `risk_report.json` remains the audit trail.

