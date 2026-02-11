from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


def _utc_now_iso() -> str:
    sde = os.getenv("SOURCE_DATE_EPOCH")
    if sde and sde.isdigit():
        return datetime.fromtimestamp(int(sde), tz=timezone.utc).isoformat()
    return datetime.now(tz=timezone.utc).isoformat()


def default_registry_root(*, artifact_root: Path | None = None) -> Path:
    rr = os.getenv("EAM_REGISTRY_ROOT")
    if rr and rr.strip():
        return Path(rr)
    ar = artifact_root or Path(os.getenv("EAM_ARTIFACT_ROOT", "/artifacts"))
    return Path(ar) / "registry"


def _jsonl_append(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            doc = json.loads(ln)
            if isinstance(doc, dict):
                out.append(doc)
    return out


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass(frozen=True)
class RegistryPaths:
    registry_root: Path
    trial_log: Path
    cards_dir: Path


def registry_paths(registry_root: Path) -> RegistryPaths:
    rr = Path(registry_root)
    return RegistryPaths(
        registry_root=rr,
        trial_log=rr / "trial_log.jsonl",
        cards_dir=rr / "cards",
    )


def new_recorded_at() -> str:
    return _utc_now_iso()

