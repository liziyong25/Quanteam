# Phase-09 (Composer/Allocator MVP)

## Goal

Implement a deterministic Composer that combines multiple Experience Cards into a new composed run (curve-level sleeve), producing:

- append-only dossier
- gate_results.json (policy-driven, deterministic)
- optional registry record + new Experience Card (Gate PASS only)

## Scope

- Add adapter `curve_composer_v1` integrated via Runner dispatch
- Add `components_integrity_v1` gate and a dedicated gate suite + policy bundle for composition
- Provide CLI: `python -m quant_eam.composer.run ...`
- Add offline e2e tests (tmp_path)
- Add docs under `docs/11_composer/`

Non-goals:

- No signal-level/order-level fusion
- No parameter search / budgeted exploration
- No Agents/LLM

## Implementation Plan

1. Resolve input `card_id` -> `primary_run_id` -> component dossier curves
2. Compose equity via aligned returns (intersection dt grid)
3. Write composed dossier (append-only), including `components.json`
4. Run GateRunner using a composer-specific gate suite
5. If `--register-card`: record TrialLog and create card only when Gate PASS

## Deliverables

- `src/quant_eam/composer/run.py`
- `src/quant_eam/backtest/curve_composer_adapter_v1.py`
- `src/quant_eam/gates/components_integrity.py`
- `policies/gate_suite_curve_composer_v1.yaml`
- `policies/policy_bundle_curve_composer_v1.yaml`
- `docs/11_composer/*`
- `tests/test_composer_e2e.py`

## Acceptance

- `pytest -q` passes (offline)
- Composer can create a composed dossier + gate_results and (on PASS) register a new card
- Append-only: rerun same inputs -> noop, no overwrites

## Execution Log

- Start Date (Asia/Taipei): 2026-02-10
- End Date (Asia/Taipei): 2026-02-10
- Commit: unknown (not creating git commits automatically)

Notes:

- `curve_composer_v1` composes existing dossier evidence; it does not call DataCatalog.
- `components_integrity_v1` enforces that components have Gate PASS evidence before composition can be registered.

## Phase-09P: Composer Hardening Patch

- Added `alignment_stats` into `components.json` to make intersection drop explicit (no silent sample loss).
- Canonicalized component ordering (`card_id/run_id`) and tightened weights validation:
  - length match
  - sum(weights)=1 with tolerance `1e-9`
  - negative weights disabled by default; can be enabled only by bundle `extensions.composer.allow_negative_weights` (v2 bundle).
- Extended `components_integrity_v1` gate params (defaults preserve v1 behavior):
  - `require_overall_pass` (default true)
  - `required_gate_ids` (default [])
  - `min_intersection_points` (default 1)
