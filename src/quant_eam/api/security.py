from __future__ import annotations

import base64
import os
import re
import secrets
from pathlib import Path

from fastapi import HTTPException, Request


_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
_JOB_ID_RE = re.compile(r"^[0-9a-f]{12}$")


def require_safe_id(value: str, *, kind: str) -> str:
    v = str(value)
    if not _ID_RE.match(v):
        raise HTTPException(status_code=400, detail=f"invalid {kind}")
    return v


def require_safe_job_id(value: str) -> str:
    v = str(value)
    if not _JOB_ID_RE.match(v):
        raise HTTPException(status_code=400, detail="invalid job_id")
    return v


def require_child_dir(parent: Path, child_name: str) -> Path:
    parent_r = parent.resolve()
    child = (parent_r / child_name).resolve()
    # Ensure child is directly under parent (no traversal).
    if child.parent != parent_r:
        raise HTTPException(status_code=400, detail="invalid path")
    return child


def enforce_write_auth(request: Request) -> None:
    """Optional lightweight auth for write endpoints (LAN hardening).

    - off (default): no auth required
    - basic: HTTP Basic auth required for write endpoints
    """
    mode = str(os.getenv("EAM_WRITE_AUTH_MODE", "off") or "off").strip().lower()
    if mode in ("", "off", "false", "0", "none"):
        return
    if mode != "basic":
        raise HTTPException(status_code=500, detail="invalid EAM_WRITE_AUTH_MODE (expected off|basic)")

    user = str(os.getenv("EAM_WRITE_AUTH_USER", "") or "").strip()
    passwd = str(os.getenv("EAM_WRITE_AUTH_PASS", "") or "").strip()
    if not user or not passwd:
        raise HTTPException(status_code=500, detail="write auth enabled but missing EAM_WRITE_AUTH_USER/EAM_WRITE_AUTH_PASS")

    auth = request.headers.get("authorization") or request.headers.get("Authorization") or ""
    if not auth.lower().startswith("basic "):
        raise HTTPException(status_code=401, detail="unauthorized", headers={"WWW-Authenticate": 'Basic realm="quant-eam-write"'})

    token = auth.split(" ", 1)[1].strip()
    try:
        decoded = base64.b64decode(token).decode("utf-8")
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=401, detail="unauthorized", headers={"WWW-Authenticate": 'Basic realm="quant-eam-write"'})

    if ":" not in decoded:
        raise HTTPException(status_code=401, detail="unauthorized", headers={"WWW-Authenticate": 'Basic realm="quant-eam-write"'})
    got_user, got_pass = decoded.split(":", 1)
    if not (secrets.compare_digest(got_user, user) and secrets.compare_digest(got_pass, passwd)):
        raise HTTPException(status_code=401, detail="unauthorized", headers={"WWW-Authenticate": 'Basic realm="quant-eam-write"'})
