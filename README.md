# Quant-EAM (Phase-00A Repo Bootstrap)

Goal: a runnable skeleton on Linux + Docker + Python, with path-aware bind mounts for `/data/quanteam/...`,
artifact persistence, and non-root file ownership.

## Quickstart (Linux, /data/quanteam)

1) Create `.env` from the example (do not commit `.env`):

```bash
make init-env
```

2) Edit `.env` and set absolute host paths + UID/GID:

- `EAM_REPO_HOST=/data/quanteam`
- `EAM_ARTIFACTS_HOST=/data/quanteam/artifacts`
- `EAM_DATA_HOST=/data/quanteam/data`
- `EAM_UID=$(id -u)`
- `EAM_GID=$(id -g)`

3) Sanity checks (creates artifacts/data dirs and checks write permissions):

```bash
make doctor
```

4) Start API (and worker service container):

```bash
make up
```

5) Verify API:

```bash
curl -s http://localhost:8000/healthz
curl -s http://localhost:8000/version
```

If port 8000 is already in use, set `EAM_API_PORT_HOST` in `.env` (default is 8000).

6) Run tests/lint/format (inside Docker):

```bash
make test
make lint
make fmt
```

7) Worker once-mode writes a bootstrap file (volume + permissions verification):

```bash
docker compose run --rm worker python -m quant_eam.worker.main --once
```

Expected host artifact path:

- `${EAM_ARTIFACTS_HOST}/bootstrap/worker_once.txt`

## Notes

- This phase intentionally does not implement any real contracts/policies schemas or backtest/data logic.
- Artifacts/data are bind-mounted so they persist on the host and do not end up in the container layer.
- Use `EAM_UID/EAM_GID` to avoid root-owned files on Linux bind mounts.
