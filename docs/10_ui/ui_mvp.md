# Web UI MVP (Read-only Review Console)

This phase adds a minimal read-only Web UI for reviewing strategy evidence without reading source code.

## SSOT and Read-only Rules

- UI is read-only: it must not write artifacts or modify any governance inputs.
- UI renders only from structured files:
  - dossier (`${EAM_ARTIFACT_ROOT}/dossiers/<run_id>/`)
  - gate results (`gate_results.json`)
  - registry (`${EAM_REGISTRY_ROOT}` or `${EAM_ARTIFACT_ROOT}/registry`)
- Any PASS/FAIL decision is displayed from **Gate + Dossier evidence** only.

## Routes

JSON API:

- `GET /runs`
- `GET /runs/{run_id}`
- `GET /runs/{run_id}/curve`
- `GET /runs/{run_id}/trades`
- `GET /runs/{run_id}/artifacts`
- `GET /registry/trials`
- `GET /registry/cards`
- `GET /registry/cards/{card_id}`

HTML UI:

- `GET /ui`
- `GET /ui/runs/{run_id}`
- `GET /ui/cards/{card_id}`

Canonical path:

- UI canonical path is `/ui` (no trailing slash).
- `/ui/` should redirect to `/ui` to avoid a nginx(302) <-> FastAPI(307) redirect loop.

Default dev ports (docker compose):

- UI: `http://localhost:${EAM_UI_PORT_HOST:-3002}/ui`
- API: `http://localhost:${EAM_API_PORT_HOST:-8002}`

LAN access:

- Ensure `.env` has `EAM_PUBLISH_IP=0.0.0.0`
- UI: `http://<LAN_IP>:${EAM_UI_PORT_HOST:-3002}/ui`
- API: `http://<LAN_IP>:${EAM_API_PORT_HOST:-8002}/runs`

## K-line Review (MVP)

On `/ui/runs/{run_id}`:

- Candlestick chart is queried via DataCatalog (no direct lake CSV reads).
- Trades markers are derived from dossier `trades.csv`.
- Holdout output is shown only as minimal summary (no holdout curve/trades rendering).

## Security Boundary

- `run_id` and `card_id` use strict allowlist validation (blocks path traversal).
- Reads are restricted to `EAM_ARTIFACT_ROOT` and `EAM_REGISTRY_ROOT` only.
