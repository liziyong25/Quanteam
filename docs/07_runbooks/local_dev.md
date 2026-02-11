# Local Dev Runbook (Linux + Docker)

This repo is designed to run in a path-aware way on Linux, commonly under `/data/quanteam/...`.

## 1) `.env` (host paths + permissions)

Create `.env` from `.env.example` and edit it:

```bash
make init-env
```

Required variables:

- `EAM_REPO_HOST`: host-side repo absolute path (e.g. `/data/quanteam`)
- `EAM_ARTIFACTS_HOST`: host-side artifacts directory (e.g. `/data/quanteam/artifacts`)
- `EAM_DATA_HOST`: host-side data directory (e.g. `/data/quanteam/data`)
- `EAM_PUBLISH_IP`: host bind IP for published ports (default `0.0.0.0` for LAN access)
- `EAM_API_PORT_HOST`: API host port (default `8002`)
- `EAM_UI_PORT_HOST`: UI host port (default `3002`)
- `EAM_UID` / `EAM_GID`: container process UID/GID, set to `id -u` / `id -g`

Why UID/GID matters: bind mounts on Linux will create files with the container's user ownership. Setting UID/GID prevents root-owned files.

## 2) Common Commands

- `make doctor`: check host directories exist and are writable
- `make up`: build and start services
- `make down`: stop services
- `make logs`: tail logs
- `make test`: run pytest (container)
- `make lint`: run ruff check (container)
- `make fmt`: run ruff format (container)
- `make docs-check`: verify docs SSOT key files exist (no docker required)

## 3) Artifacts/Data Persistence

- Container path `/artifacts` is bind-mounted to `${EAM_ARTIFACTS_HOST}`
- Container path `/data` is bind-mounted to `${EAM_DATA_HOST}`

For Phase-00A worker, once-mode writes:

- `/artifacts/bootstrap/worker_once.txt` -> `${EAM_ARTIFACTS_HOST}/bootstrap/worker_once.txt`

## 4) Default URLs

- UI (nginx proxy): `http://localhost:3002/ui`
- API (direct): `http://localhost:8002/healthz` and `http://localhost:8002/runs`

Notes on ports:

- Container ports are normalized:
  - API listens on container `8000`
  - UI nginx listens on container `80`
- Host ports `8002/3002` are published ports only (so you will not see `8002/3002` inside containers).

## 5) LAN Access (from another machine)

If you want to access from another machine on the same LAN, keep `EAM_PUBLISH_IP=0.0.0.0` and use the host LAN IP:

```bash
hostname -I
```

Example:

- UI: `http://<LAN_IP>:3002/ui`
- API: `http://<LAN_IP>:8002/healthz`
