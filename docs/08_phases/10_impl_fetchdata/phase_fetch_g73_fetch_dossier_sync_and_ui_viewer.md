# Phase Fetch G73: Fetch Dossier Sync and Job UI Evidence Viewer

## 1) Goal
Implement deterministic fetch evidence sync into dossier and render dossier-based fetch evidence in job UI as read-only viewer.

## 2) Requirements
- MUST mirror fetch evidence from job outputs into dossier fetch root.
- MUST keep dossier evidence append-only and hash-linked.
- MUST render fetch steps/evidence in `/ui/jobs/{job_id}` read-only page.
- MUST NOT modify `contracts/**`, `policies/**`, or holdout visibility scope.

## 3) Architecture & Interfaces
- Inputs:
  - `docs/05_data_plane/qa_fetch_dossier_evidence_contract_v1.md`
  - orchestrator run completion outputs (`outputs/fetch/*`)
- Outputs:
  - dossier-local `fetch/*` evidence synced before review/gates
  - UI job page fetch evidence viewer

## 4) Out-of-scope
- New fetch provider integrations.
- Strategy/backtest behavior changes.
- Any policy/contract mutation.

## 5) DoD
- `python3 scripts/check_docs_tree.py`
- `docker compose run --rm api pytest -q tests/test_orchestrator_fetch_dossier_sync_phase73.py tests/test_ui_fetch_evidence_viewer_phase73.py`

## 6) Implementation Plan
### 6.1 Execution Strategy
- Add orchestrator-side sync to mirror `jobs/<job_id>/outputs/fetch/*` into `artifacts/dossiers/<run_id>/fetch/` on run completion.
- Rewrite `fetch_steps_index.json` step file paths to dossier-local files when syncing.
- Update dossier manifest artifacts/hashes for copied fetch evidence.
- Extend `/ui/jobs/{job_id}` to render a read-only dossier fetch evidence viewer from `fetch_steps_index.json`.

### 6.2 Controller Execution Record
- Published packet task card: `artifacts/subagent_control/G73/task_card.yaml`.
- Updated orchestrator run completion path in `src/quant_eam/orchestrator/workflow.py`.
- Updated UI context/rendering in:
  - `src/quant_eam/api/ui_routes.py`
  - `src/quant_eam/ui/templates/job.html`
- Added regression coverage:
  - `tests/test_orchestrator_fetch_dossier_sync_phase73.py`
  - `tests/test_ui_fetch_evidence_viewer_phase73.py`

### 6.3 Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `docker compose run --rm api pytest -q tests/test_orchestrator_fetch_dossier_sync_phase73.py tests/test_ui_fetch_evidence_viewer_phase73.py` passed (`2 passed`).
- `python3 scripts/check_subagent_packet.py --phase-id G73` passed via packet runner finish lifecycle.
