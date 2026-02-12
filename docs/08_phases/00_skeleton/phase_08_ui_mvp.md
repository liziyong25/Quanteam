# Phase-08: Web UI MVP (Read-only Review Console)

## Goal

- Provide a minimal Web UI to review strategy evidence:
  - Dossier (SSOT)
  - GateResults
  - Registry (TrialLog + Cards)
- UI must be read-only and must not write artifacts.

## Scope

In scope:

- Read-only JSON API endpoints for runs/dossiers and registry
- HTML UI pages for listing and inspecting runs/cards
- Minimal charts (equity curve + K-line) with offline rendering (no CDN)
- Offline tests (tmp_path)
- Docs + phase log

Out of scope:

- Auth/multi-user
- Any write operations from UI
- Agents/LLM

## Acceptance

- `/ui` and `/ui/runs/{run_id}` return 200 and render evidence from dossier/registry files only
- Path traversal is blocked
- Holdout output is shown only as minimal summary (no holdout curve/trades rendering)
- `pytest -q` passes

## Execution Log

- Start Date (Asia/Taipei): 2026-02-10
- End Date (Asia/Taipei): 2026-02-10
- Commit: unknown (repo has no git metadata or HEAD not available)

## Phase-08P: Ports Normalize Patch

Background:

- Redirect loop existed:
  - nginx: `/ui` -> (302) `/ui/`
  - FastAPI: `/ui/` -> (307) `/ui`
  - Result: `/ui` (302) -> `/ui/` (307) -> `/ui` ... infinite loop.
- Root cause: slash canonicalization rules were fighting each other.

Ports (normalized container ports; published host ports stay the same):

- Container (fixed):
  - API listens on `8000`
  - UI nginx listens on `80`
- Host published ports default:
  - API: `8002` -> container `8000`
  - UI: `3002` -> nginx `80` -> api `8000`
- LAN bind IP is controlled by `.env` `EAM_PUBLISH_IP` (default `0.0.0.0`).

Redirect canonicalization fix (canonical path: `/ui`):

- nginx no longer redirects `/ui` -> `/ui/`
- nginx redirects `/ui/` -> `/ui` (single hop) to avoid triggering FastAPI's 307 normalization loop

Acceptance evidence (2026-02-10):

1) Build + start:

```bash
docker compose up -d --build
docker compose ps
```

Observed ports:

- `api`: `0.0.0.0:8002->8000/tcp`
- `ui`: `0.0.0.0:3002->80/tcp`

2) Redirect loop gone (LAN IP example `192.168.31.83`):

```bash
curl -sIL --max-redirs 5 http://192.168.31.83:3002/ui  | egrep 'HTTP/|Location:'
curl -sIL --max-redirs 5 http://192.168.31.83:3002/ui/ | egrep 'HTTP/|Location:'
```

Observed:

- `/ui` final `200`
- `/ui/` `308 Location: /ui` then `200`

3) API reachable (LAN):

```bash
curl -s http://192.168.31.83:8002/healthz
```

Observed: `{"status":"ok"}`

4) Regression gates:

```bash
EAM_UID=$(id -u) EAM_GID=$(id -g) docker compose run --rm api pytest -q
python3 scripts/check_docs_tree.py
```

Observed: `47 passed` and `docs tree: OK`
