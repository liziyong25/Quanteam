from __future__ import annotations

import argparse
import os
import time
from datetime import datetime, timezone
from pathlib import Path
import json

from quant_eam.core.version import get_version


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def bootstrap_once() -> Path:
    artifact_root = Path(os.getenv("EAM_ARTIFACT_ROOT", "/artifacts"))
    env = os.getenv("EAM_ENV", "dev")

    out_dir = artifact_root / "bootstrap"
    out_dir.mkdir(parents=True, exist_ok=True)

    out_path = out_dir / "worker_once.txt"
    content = "\n".join(
        [
            f"timestamp={_now_iso()}",
            f"version={get_version()}",
            f"eam_env={env}",
            f"uid={os.getuid()}",
            f"gid={os.getgid()}",
            "",
        ]
    )
    out_path.write_text(content, encoding="utf-8")
    return out_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="quant_eam.worker")
    parser.add_argument("--once", action="store_true", help="Run one bootstrap pass and exit.")
    parser.add_argument("--run-jobs", action="store_true", help="Advance orchestrator jobs under EAM_JOB_ROOT.")
    args = parser.parse_args(argv)

    if args.run_jobs:
        from quant_eam.orchestrator.workflow import advance_all_once

        if args.once:
            res = advance_all_once()
            print(json.dumps({"mode": "run-jobs", "once": True, "results": res}, indent=2, sort_keys=True))
            return 0

        print("[worker] started (run-jobs daemon mode). Use --once to advance once and exit.")
        while True:
            advance_all_once()
            time.sleep(5)

    if args.once:
        path = bootstrap_once()
        print(f"[worker] wrote bootstrap file: {path}")
        return 0

    # Default mode: keep the process alive (no external service dependency in Phase-00A).
    print("[worker] started (daemon mode). Use --once to write bootstrap file and exit.")
    while True:
        time.sleep(60)


if __name__ == "__main__":
    raise SystemExit(main())
