#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path


PROMPT_FILE_RE = re.compile(r"^prompt_v([1-9][0-9]*)\.md$")


def _parse_front_matter(md: str) -> dict[str, str]:
    """Parse the small key: value header before the first '---' line."""
    out: dict[str, str] = {}
    for ln in md.splitlines():
        if ln.strip() == "---":
            break
        if ":" not in ln:
            continue
        k, v = ln.split(":", 1)
        k = k.strip()
        v = v.strip()
        if k:
            out[k] = v
    return out


def main() -> int:
    repo_root = Path.cwd()
    agents_dir = repo_root / "prompts" / "agents"
    if not agents_dir.is_dir():
        print("ERROR: missing prompts/agents directory", file=sys.stderr)
        return 2

    errors: list[str] = []

    agent_dirs = sorted([p for p in agents_dir.iterdir() if p.is_dir()], key=lambda p: p.name)
    if not agent_dirs:
        errors.append("no agent prompt directories found under prompts/agents")

    for d in agent_dirs:
        prompt_files: list[tuple[int, Path]] = []
        for p in sorted([pp for pp in d.iterdir() if pp.is_file()], key=lambda p: p.name):
            m = PROMPT_FILE_RE.match(p.name)
            if not m:
                continue
            prompt_files.append((int(m.group(1)), p))

        if not prompt_files:
            errors.append(f"{d.as_posix()}: missing prompt_v{{n}}.md files")
            continue

        versions = sorted(v for v, _p in prompt_files)
        expected = list(range(1, max(versions) + 1))
        if versions != expected:
            errors.append(f"{d.as_posix()}: non-consecutive prompt versions (found={versions}, expected={expected})")

        for v, p in prompt_files:
            txt = p.read_text(encoding="utf-8")
            fm = _parse_front_matter(txt)
            pv = fm.get("prompt_version")
            osv = fm.get("output_schema_version")
            if pv != f"v{v}":
                errors.append(f"{p.as_posix()}: prompt_version must equal v{v} (got={pv!r})")
            if not isinstance(osv, str) or not osv.strip():
                errors.append(f"{p.as_posix()}: missing output_schema_version")
            if "---" not in txt.splitlines()[:10]:
                errors.append(f"{p.as_posix()}: missing '---' delimiter near top (front matter not terminated)")

    if errors:
        print("prompts tree: INVALID", file=sys.stderr)
        for e in errors:
            print(f"- {e}", file=sys.stderr)
        return 2

    print("prompts tree: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
