#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Promote a recorded cassette.jsonl into a deterministic fixtures location (Phase-28).")
    ap.add_argument("--from", dest="src", required=True, help="source cassette.jsonl path")
    ap.add_argument("--agent", required=True, help="agent id (e.g. intent_agent_v1)")
    ap.add_argument("--case", required=True, help="case name (e.g. ma_crossover_case)")
    ap.add_argument("--dest-root", default="tests/fixtures/cassettes", help="destination root (default: tests/fixtures/cassettes)")
    args = ap.parse_args(argv)

    src = Path(str(args.src)).resolve()
    if not src.is_file():
        raise SystemExit(f"cassette not found: {src.as_posix()}")
    agent = str(args.agent).strip()
    case = str(args.case).strip()
    if not agent or not case:
        raise SystemExit("agent and case must be non-empty")

    dest_root = Path(str(args.dest_root))
    dest = dest_root / agent / case / "cassette.jsonl"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    print(dest.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

