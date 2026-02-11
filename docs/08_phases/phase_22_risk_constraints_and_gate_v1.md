# Phase-22: Risk/Constraints Enforcement v1

## Goal

- Make `risk_policy_v1` enforceable via deterministic Gate + Dossier evidence.
- Produce `risk_report.json` for UI review.
- Add gate `risk_policy_compliance_v1` with clear FAIL vs INVALID semantics.

## Changes

- Code:
  - Added gate `risk_policy_compliance_v1` (computes + writes `risk_report.json`).
  - Registered the gate in `src/quant_eam/gates/registry.py`.
  - Added the gate to gaterunner mandatory gates (vectorbt adapter).
- UI:
  - Run detail page renders a Risk block when `risk_report.json` exists.
- Docs:
  - Added gate spec doc and backtest-plane risk evidence doc.

## Semantics (MVP)

- FAIL: risk non-compliance (threshold exceeded, or short exposure when `allow_short=false`).
- INVALID: missing evidence inputs (curve/trades), missing runspec test segment fields, or DataCatalog query returns 0 rows.

## Acceptance Evidence

Run:

```bash
EAM_UID=$(id -u) EAM_GID=$(id -g) docker compose run --rm api pytest -q
python3 scripts/check_docs_tree.py
```

Manual spot-check (example LAN/local):

```bash
python -m quant_eam.data_lake.demo_ingest --snapshot-id demo_snap_phase22_001
python -m quant_eam.compiler.compile --blueprint contracts/examples/blueprint_buyhold_demo_ok.json --snapshot-id demo_snap_phase22_001 --out /tmp/runspec.json --policy-bundle policies/policy_bundle_v1.yaml
python -m quant_eam.runner.run --runspec /tmp/runspec.json --policy-bundle policies/policy_bundle_v1.yaml
# pick dossier dir under /artifacts/dossiers/<run_id> then:
python -m quant_eam.gaterunner.run --dossier /artifacts/dossiers/<run_id> --policy-bundle policies/policy_bundle_v1.yaml
ls -la /artifacts/dossiers/<run_id>/risk_report.json
```

## Files Touched

- `src/quant_eam/gates/risk_policy_compliance.py`
- `src/quant_eam/gates/registry.py`
- `src/quant_eam/gaterunner/run.py`
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/run.html`
- `docs/06_backtest_plane/risk_constraints_v1.md`
- `docs/08_gates/risk_policy_compliance_v1.md`
- `docs/08_phases/phase_22_risk_constraints_and_gate_v1.md`
- `scripts/check_docs_tree.py`

