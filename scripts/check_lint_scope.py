#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path


PLAN_PATH = Path("docs/07_runbooks/lint_coverage_plan.md")


def _extract_yaml_block(text: str) -> str | None:
    m = re.search(r"```yaml\n(.*?)\n```", text, flags=re.DOTALL)
    if not m:
        return None
    return m.group(1)


def _parse_simple_yaml_list(block: str, key: str) -> list[str] | None:
    # Minimal parser: find "key:" then collect "- item" lines until next top-level key.
    lines = block.splitlines()
    out: list[str] = []
    in_key = False
    for line in lines:
        if re.match(r"^[A-Za-z0-9_]+:\s*$", line.strip()):
            in_key = line.strip().startswith(f"{key}:")
            continue
        if not in_key:
            continue
        m = re.match(r"^\s*-\s+(.*)\s*$", line)
        if m:
            out.append(m.group(1).strip())
    return out if out else None


def main() -> int:
    if not PLAN_PATH.is_file():
        print(f"ERROR: missing lint coverage plan: {PLAN_PATH}", file=sys.stderr)
        return 2

    text = PLAN_PATH.read_text(encoding="utf-8")
    block = _extract_yaml_block(text)
    if not block:
        print("ERROR: lint_coverage_plan.md missing ```yaml ... ``` block", file=sys.stderr)
        return 2

    if "version: lint_coverage_plan_v1" not in block:
        print("ERROR: yaml block missing version: lint_coverage_plan_v1", file=sys.stderr)
        return 2

    cur = _parse_simple_yaml_list(block, "current_in_ci_local")
    nxt = _parse_simple_yaml_list(block, "next_expand")
    if not cur:
        print("ERROR: yaml block missing current_in_ci_local list", file=sys.stderr)
        return 2
    if not nxt:
        print("ERROR: yaml block missing next_expand list", file=sys.stderr)
        return 2

    # Sanity: lists should not be empty and must be relative paths.
    bad: list[str] = []
    for s in cur + nxt:
        if s.startswith("/") or s.startswith(".."):
            bad.append(s)
    if bad:
        print("ERROR: plan contains non-repo-relative paths:", file=sys.stderr)
        for s in bad:
            print(f"- {s}", file=sys.stderr)
        return 2

    print("lint scope plan: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
