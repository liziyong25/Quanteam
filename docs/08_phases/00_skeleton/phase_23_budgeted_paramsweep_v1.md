# Phase-23: Budgeted ParamSweep v1

## Goal

- Add deterministic parameter sweep (grid search) governed by `budget_policy_v1`.
- Produce append-only sweep evidence (`trials.jsonl` + `leaderboard.json`) referencing dossiers.
- Allow spawning the best candidate as a new child job (returns to blueprint approval checkpoint).
- Ensure holdout remains minimal-only (no leakage of holdout internals into tuning loop).

## Changes

- Orchestrator:
  - Added `src/quant_eam/orchestrator/param_sweep.py` to run deterministic grid sweeps and write evidence under job outputs.
  - Extended `src/quant_eam/orchestrator/workflow.py` to add a new approval checkpoint `WAITING_APPROVAL(step=sweep)` when `sweep_spec` is present.
- JobStore:
  - Added `spawn_child_job_from_sweep_best` (budget-enforced) to spawn the best sweep candidate as a new job with lineage.
- API/UI:
  - Added `POST /jobs/{job_id}/spawn_best`
  - Added `GET /jobs/{job_id}/sweep/leaderboard`
  - UI job page shows sweep progress and supports “Spawn Best Candidate”.
- Contracts (workflow evidence):
  - `contracts/sweep_trial_schema_v1.json`
  - `contracts/leaderboard_schema_v1.json`

## Acceptance Evidence

Run:

```bash
EAM_UID=$(id -u) EAM_GID=$(id -g) docker compose run --rm api pytest -q
python3 scripts/check_docs_tree.py
```

Manual smoke (example):

```bash
# Create a job from a blueprint that contains blueprint.extensions.sweep_spec
# Advance worker until it blocks at WAITING_APPROVAL(step=sweep), then approve sweep:
curl -X POST http://localhost:8002/jobs/<job_id>/approve?step=sweep

# After sweep completes:
curl -s http://localhost:8002/jobs/<job_id>/sweep/leaderboard | jq .
curl -X POST http://localhost:8002/jobs/<job_id>/spawn_best
```

## Files Touched

- `src/quant_eam/orchestrator/param_sweep.py`
- `src/quant_eam/orchestrator/workflow.py`
- `src/quant_eam/jobstore/store.py`
- `src/quant_eam/api/jobs_api.py`
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/job.html`
- `contracts/sweep_trial_schema_v1.json`
- `contracts/leaderboard_schema_v1.json`
- `docs/12_workflows/param_sweep_v1.md`
- `docs/08_phases/00_skeleton/phase_23_budgeted_paramsweep_v1.md`
- `scripts/check_docs_tree.py`

