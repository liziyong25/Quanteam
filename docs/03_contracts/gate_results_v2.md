# Gate Results v2

## Purpose

`gate_results_v2` is the **GateRunner output** contract. It is the arbitration evidence that later promotion/registry actions must reference.

Producer: `quant_eam.gaterunner`  
Consumers: UI (read-only), Registry (TrialLog), promotion logic (future)

Hard boundaries:

- PASS/FAIL must reference dossier artifacts (evidence chain).
- Holdout output must stay **minimal** (pass/fail + tiny summary only). No curves/trades.

## Key Fields

- `schema_version`: must be `"gate_results_v2"`.
- `run_id`: dossier run id.
- `gate_suite_id`: policy gate suite id that declared the gates.
- `overall_pass`: overall arbitration result.
- `results[]`: run-level gate results.
- `segment_results[]` (optional):
  - Per-segment gate results and segment evidence refs (typically under `segments/<segment_id>/...`).
  - This closes the v1 gray area where segment results were placed under `extensions`.
- `holdout_summary` (optional): minimal-only.

## Examples

- OK: `contracts/examples/gate_results_v2_ok.json`
- BAD: `contracts/examples/gate_results_v2_bad.json`

