#!/usr/bin/env bash
set -euo pipefail

make init-env
if [ -f .env ]; then
  set -a
  # shellcheck source=/dev/null
  source .env
  set +a
fi
make doctor
make up

# Smoke: API reachable and UI canonicalization does not loop.
curl -fsS "http://localhost:${EAM_API_PORT_HOST:-8002}/healthz" | grep -q '"status":"ok"' || {
  echo "healthz failed" >&2
  exit 1
}
curl -fsSIL --max-redirs 5 "http://localhost:${EAM_UI_PORT_HOST:-3002}/ui" | grep -Eq '^HTTP/.* 200' || {
  echo "/ui did not resolve to 200 within 5 redirects" >&2
  exit 1
}
curl -fsSIL --max-redirs 5 "http://localhost:${EAM_UI_PORT_HOST:-3002}/ui/" | grep -Eq '^HTTP/.* (200|308)' || {
  echo "/ui/ did not resolve to 200 or 308 within 5 redirects" >&2
  exit 1
}

make test
make lint
make fmt

docker compose run --rm worker python -m quant_eam.worker.main --once
