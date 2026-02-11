# Risk Evidence Artifacts v1

Goal: align risk gates with **backtest-produced** intermediate evidence so that risk arbitration cannot drift from the engine behavior.

## Produced By

Producer: Runner + backtest adapter (`vectorbt_signal_v1` deterministic engine)

Written into dossier directory (append-only):

- `positions.csv`
- `turnover.csv`
- `exposure.json`

## Files

### positions.csv

Long format, one row per `(dt, symbol)`:

- `dt` (ISO 8601)
- `symbol`
- `qty`
- `close`
- `position_value`
- `equity` (repeated per row for auditing)

### turnover.csv

One row per `dt`:

- `dt` (ISO 8601)
- `turnover` (float, may be empty for first bar)

Definition (MVP): `abs(traded_notional)` / `prev_equity`, using the engine's execution fill price.

### exposure.json

Summary evidence derived by the engine:

- `schema_version`: `backtest_exposure_v1` (internal evidence marker, not a cross-module contract)
- `adapter_id`, `strategy_id`
- `dt_min`, `dt_max`
- `max_observed`:
  - `max_leverage_observed`
  - `max_positions_observed`
  - `max_turnover_observed`

## Used By

- Gate: `risk_policy_compliance_v1` must use these artifacts as its source of truth.
- `risk_report.json` must reference these artifacts (evidence chain).

