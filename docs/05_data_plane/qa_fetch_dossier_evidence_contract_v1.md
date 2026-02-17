# QA Fetch Dossier Evidence Contract v1

## Purpose

Freeze deterministic dossier-local fetch evidence layout and read-only UI viewer requirements for audit/review checkpoints.

## Dossier Fetch Layout

Required root:

- `artifacts/dossiers/<run_id>/fetch/`

Required files:

- `fetch_steps_index.json`
- `fetch_request.json`
- `fetch_result_meta.json`
- `fetch_preview.csv`
- `fetch_error.json` (only when final fetch status is failure)

Optional multi-step files (append-only):

- `step_XXX_fetch_request.json`
- `step_XXX_fetch_result_meta.json`
- `step_XXX_fetch_preview.csv`
- `step_XXX_fetch_error.json`

## Sync Rule

- Source evidence may originate from `jobs/<job_id>/outputs/fetch/`.
- Orchestrator MUST mirror/canonicalize fetch evidence into dossier fetch root before gate review.
- Dossier fetch evidence is append-only and read-only for UI.

## Viewer Contract

- UI must render `fetch_steps_index.json` first.
- Each step must expose:
  - `step_index`
  - `step_kind`
  - `status`
  - request/meta/preview/error file references
- Viewer must not provide write actions.

## Governance

- This contract is docs-only governance freeze for skeleton track.
- Runtime implementation and UI wiring are handled by impl track goals.
