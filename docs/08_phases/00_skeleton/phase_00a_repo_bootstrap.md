# Phase-00A: Repo Bootstrap (path-aware)

## 1) 目标（Goal）

- Provide a runnable skeleton in Docker: FastAPI `api` + `worker` + tests + ruff + Makefile + docker compose.
- Ensure path-aware bind mounts via `.env` for `/data/quanteam/...` and non-root file ownership.

## 2) 范围（Scope）

### In Scope

- FastAPI endpoints: `/healthz`, `/version`
- Worker once-mode: write a bootstrap file into artifacts volume
- Tooling: pytest + ruff + Makefile
- docker compose: volumes + user mapping controlled by `.env`

### Out of Scope

- No real contracts/policies schemas and no real backtest/data logic

## 3) Execution Log (真实执行记录)

Environment:

- OS: Ubuntu 24.04.3 LTS
- Docker: 28.2.2
- Docker Compose: v5.0.2
- Mode: rootless docker daemon

Key events:

1) `make up` initially failed because Docker daemon endpoint was not reachable (rootless socket not running).
2) After starting rootless docker daemon, `make up` failed with port conflict:
   - Error: `listen tcp4 0.0.0.0:8000: bind: address already in use`
   - Root cause: rootless RootlessKit port forwarding could not bind host port 8000.
   - Resolution: set `.env` `EAM_API_PORT_HOST` to a free port (example: `18000`) and map `${EAM_API_PORT_HOST}:8000`.

Validation results:

- `pytest`: `3 passed`
- `ruff check`: `All checks passed!`
- `ruff format`: `9 files left unchanged` (after formatting stabilized)
- Worker once-mode:
  - Command: `docker compose run --rm worker python -m quant_eam.worker.main --once`
  - Output: wrote `/artifacts/bootstrap/worker_once.txt`

Artifacts:

- Host path: `${EAM_ARTIFACTS_HOST}/bootstrap/worker_once.txt`

## 4) Open Issues

- [ ] Default host port 8000 may conflict on some machines. Recommend setting `.env` `EAM_API_PORT_HOST`.

