# Phase-24: Attribution + Diagnostics v1

## Goal

- Add deterministic performance attribution + diagnostics as dossier evidence:
  - `attribution_report.json`
  - `reports/attribution/report.md`
- Render attribution on UI Run/Card pages (read-only).
- No external data dependencies or network IO.

## Changes

- Code:
  - Added `src/quant_eam/analysis/attribution_v1.py` to generate append-only attribution artifacts from dossier inputs.
  - Updated `src/quant_eam/agents/report_agent.py` to generate Phase-24 attribution evidence into the dossier (best-effort).
- UI:
  - Run page renders an Attribution block when `attribution_report.json` exists.
  - Card page shows a minimal Attribution preview for the primary run when present.
- Contracts:
  - Added optional contract schema `contracts/attribution_report_schema_v1.json` (used via forced-schema validation in tests).
- Tests:
  - Added offline test that builds a demo run dossier, generates attribution evidence, validates schema, and asserts UI rendering.
- Docs:
  - Added `docs/06_backtest_plane/attribution_v1.md` and referenced it from `docs/06_backtest_plane/backtest_index.md`.

## Evidence / Artifacts

Under `artifacts/dossiers/<run_id>/`:

- `attribution_report.json`
- `reports/attribution/report.md`

## Acceptance Evidence

Run:

```bash
EAM_UID=$(id -u) EAM_GID=$(id -g) docker compose run --rm api pytest -q
python3 scripts/check_docs_tree.py
```

## Files Touched

- `src/quant_eam/analysis/attribution_v1.py`
- `src/quant_eam/agents/report_agent.py`
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/run.html`
- `src/quant_eam/ui/templates/card.html`
- `contracts/attribution_report_schema_v1.json`
- `tests/test_attribution_phase24.py`
- `docs/06_backtest_plane/attribution_v1.md`
- `docs/06_backtest_plane/backtest_index.md`
- `docs/08_phases/phase_24_attribution_and_diagnostics_v1.md`
- `scripts/check_docs_tree.py`

---

# Codex Phase Prompt Footer (Appendix, SSOT)

## Required Reading (SSOT)

- `docs/01_governance.md`
- `docs/02_protocols.md`
- The current phase log under `docs/08_phases/` (create/update it)

## Required Deliverables

- Code (only within allowed change scope for this phase)
- Tests (if code changes impact behavior)
- Docs: update `docs/08_phases/phase_XX_*.md` with execution log and acceptance evidence
- ADR: required when changing any boundary/protocol of contracts/policies/dossier/gates/holdout/determinism

## Hard No (Non-Negotiables)

- Policies are read-only references by `policy_id`. No overriding or inline policy edits in strategy modules.
- Strategy generation must output **Blueprint/DSL** (declarative). No direct executable strategy scripts that bypass the compiler/kernel.
- Arbitration is only via **Gate + Dossier**:
  - PASS/FAIL/registry writes must reference dossier artifacts.
  - Agents must never "decide"; they can propose or analyze only.
- Final Holdout isolation:
  - Must not leak holdout internals into iterative loops.
  - Holdout output is restricted: pass/fail + minimal summary only.
- Dossier is append-only:
  - No rewriting past runs, no overwriting artifacts; new runs create new dossiers.
- Budget/stop conditions are mandatory to prevent unbounded search.
- Every agent must be harnessed:
  - Input/output schema, tests, deterministic replay, and recorded artifacts.

## Acceptance (Evidence Checklist)

- `docker compose up -d` works (if this phase includes runtime changes)
- `pytest -q` passes
- Artifacts path list (host + container mapping) is stated and verified
