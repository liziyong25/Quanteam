from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

import yaml


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def find_repo_root() -> Path:
    candidates: list[Path] = []
    env_root = os.getenv("EAM_REPO")
    if env_root:
        candidates.append(Path(env_root))
    cwd = Path.cwd()
    candidates.append(cwd)
    candidates.extend(cwd.parents)

    here = Path(__file__).resolve()
    candidates.append(here)
    candidates.extend(here.parents)

    for c in candidates:
        if c.is_dir() and (c / "policies").is_dir():
            return c
    return cwd


def default_policies_dir() -> Path:
    return find_repo_root() / "policies"


def iter_policy_assets(policies_dir: Path) -> list[Path]:
    """Return policy asset files under policies_dir, excluding policies/examples/*."""
    assets: list[Path] = []
    for p in sorted(policies_dir.glob("*.y*ml")):
        if p.is_file():
            assets.append(p)
    return assets


def iter_policy_examples(policies_dir: Path) -> list[Path]:
    examples_dir = policies_dir / "examples"
    if not examples_dir.is_dir():
        return []
    return sorted([p for p in examples_dir.glob("*.y*ml") if p.is_file()])
