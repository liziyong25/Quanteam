from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PromptPack:
    path: Path
    prompt_version: str
    output_schema_version: str
    system: str


def _find_repo_root(start: Path) -> Path:
    cur = start.resolve()
    for p in [cur, *cur.parents]:
        if (p / "pyproject.toml").is_file() and (p / "src").is_dir():
            return p
    return cur


def _parse_header(text: str) -> tuple[dict[str, str], str]:
    """Parse a minimal header then return (meta, body).

    Format:
      key: value
      key2: value2
      ---
      body...
    """
    lines = text.splitlines()
    meta: dict[str, str] = {}
    body_start = 0
    for i, ln in enumerate(lines):
        if ln.strip() == "---":
            body_start = i + 1
            break
        if ":" not in ln:
            # Stop at first non header-ish line.
            body_start = i
            break
        k, v = ln.split(":", 1)
        k = k.strip()
        v = v.strip()
        if k:
            meta[k] = v
    body = "\n".join(lines[body_start:]).strip() + "\n"
    return meta, body


def load_promptpack(*, agent_id: str, version: str, root: Path | None = None) -> PromptPack:
    """Load a versioned promptpack for an agent.

    Root defaults to repo_root/prompts/agents.
    """
    agent_id = str(agent_id).strip()
    version = str(version).strip()
    if not version.startswith("v"):
        version = f"v{version}"

    if root is None:
        repo_root = _find_repo_root(Path.cwd())
        root = repo_root / "prompts" / "agents"

    p = Path(root) / agent_id / f"prompt_{version}.md"
    if not p.is_file():
        raise FileNotFoundError(p.as_posix())

    text = p.read_text(encoding="utf-8")
    meta, body = _parse_header(text)
    prompt_version = str(meta.get("prompt_version") or version).strip() or version
    out_schema = str(meta.get("output_schema_version") or "").strip()
    if not out_schema:
        raise ValueError("promptpack missing output_schema_version")

    return PromptPack(path=p, prompt_version=prompt_version, output_schema_version=out_schema, system=body)


def default_prompt_version() -> str:
    return "v1"

