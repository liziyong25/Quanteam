# Troubleshooting

## 1) Port 8002/3002 Already In Use (rootless docker, RootlessKit)

Symptom:

- `make up` fails with something like: `listen tcp4 0.0.0.0:8002: bind: address already in use`
- Often shown as: `RootlessKit PortManager.AddPort() ... bind: address already in use`

Diagnosis:

```bash
ss -ltnp | grep -E ':(8002|3002)\\b' || true
```

Optional (if installed):

```bash
lsof -i :8002 || true
lsof -i :3002 || true
```

Fix:

- Set `.env`:
  - `EAM_PUBLISH_IP=0.0.0.0` for LAN access (or `127.0.0.1` for local-only)
  - `EAM_API_PORT_HOST` to an available port (default `8002`)
  - `EAM_UI_PORT_HOST` to an available port (default `3002`)
- Then run `make up`.

## 2) `/ui` Redirect Loop (302/307 ping-pong)

Symptom:

- Opening `http://<LAN_IP>:3002/ui` never loads, and `curl -IL` shows repeating redirects.

Diagnosis:

```bash
curl -sIL --max-redirs 10 http://<LAN_IP>:3002/ui | egrep 'HTTP/|Location:'
```

Typical bad pattern (loop):

- nginx: `/ui` -> (302) `/ui/`
- FastAPI: `/ui/` -> (307) `/ui`

Fix (canonicalize to `/ui`):

- nginx must not redirect `/ui` to `/ui/`
- optionally redirect `/ui/` to `/ui` (single hop, no loop)

## 3) Permission Issues (root-owned files on host)

Symptom:

- Files under `${EAM_ARTIFACTS_HOST}` or `${EAM_DATA_HOST}` become owned by `root:root`
- You cannot edit or remove generated files without sudo

Fix:

- Set `.env`:
  - `EAM_UID=$(id -u)`
  - `EAM_GID=$(id -g)`
- Re-run `make down && make up`

Diagnosis helpers:

```bash
id -u
id -g
ls -la artifacts data 2>/dev/null || true
```
