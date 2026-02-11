from __future__ import annotations

import os
from importlib import metadata

__version__ = "0.0.0"


def get_version() -> str:
    try:
        return metadata.version("quant-eam")
    except metadata.PackageNotFoundError:
        return __version__


def get_git_sha() -> str | None:
    sha = os.getenv("EAM_GIT_SHA") or os.getenv("GIT_SHA")
    if not sha:
        return None
    sha = sha.strip()
    return sha or None


def version_payload() -> dict:
    payload: dict = {"version": get_version()}
    sha = get_git_sha()
    if sha is not None:
        payload["git_sha"] = sha
    return payload
