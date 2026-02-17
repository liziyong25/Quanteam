from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from quant_eam.index.indexer import build_all_indexes


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m quant_eam.index.cli")
    p.add_argument(
        "--artifact-root",
        default=None,
        help="Artifact root to scan (default: env EAM_ARTIFACT_ROOT or /artifacts).",
    )
    args = p.parse_args(argv)

    ar = Path(args.artifact_root) if args.artifact_root else None
    res = build_all_indexes(artifact_root_dir=ar)
    sys.stdout.write(json.dumps(res, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

