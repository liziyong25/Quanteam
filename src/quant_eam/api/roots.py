from __future__ import annotations

import os
from pathlib import Path


def artifact_root() -> Path:
    return Path(os.getenv("EAM_ARTIFACT_ROOT", "/artifacts"))


def dossiers_root() -> Path:
    return artifact_root() / "dossiers"


def registry_root() -> Path:
    rr = os.getenv("EAM_REGISTRY_ROOT")
    if rr and rr.strip():
        return Path(rr)
    return artifact_root() / "registry"

