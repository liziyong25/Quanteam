# Gate: risk_policy_compliance_v1

## Purpose

Enforce `risk_policy_v1` declarative thresholds against a run dossier and produce deterministic evidence.

## Inputs

- Policies (read-only, referenced via bundle):
  - `risk_policy_v1` (max_leverage/max_positions/max_turnover/(optional max_drawdown))
  - `execution_policy_v1` (enforces `allow_short`)
- Dossier artifacts:
  - `positions.csv` (Phase-27 risk evidence)
  - `turnover.csv` (Phase-27 risk evidence)
  - `exposure.json` (Phase-27 risk evidence summary)
  - `config_snapshot.json` (for runspec + DataCatalog root)

## Outputs

- Gate result entry in `gate_results.json`
- Evidence file written to dossier (append-only new artifact):
  - `risk_report.json`

## Decision Semantics

- PASS: no violations observed.
- FAIL: violations observed (risk non-compliance). This is a normal strategy rejection, not a system error.
- INVALID: reserved for missing evidence or inability to compute (e.g. missing `curve.csv`, missing runspec test segment fields, DataCatalog query returns 0 rows).

## Evidence Notes

`risk_report.json` is computed deterministically from:

- backtest-produced risk evidence artifacts:
  - `positions.csv`
  - `turnover.csv`
  - `exposure.json`

This closes the drift risk where risk gates could diverge from the backtest engine behavior.
