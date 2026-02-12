#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    src_root = repo_root / "src"
    if src_root.as_posix() not in sys.path:
        sys.path.insert(0, src_root.as_posix())

    from quant_eam.qa_fetch.probe import (
        DEFAULT_EXPECTED_COUNT,
        DEFAULT_MATRIX_V3_PATH,
        DEFAULT_OUTPUT_DIR,
        probe_matrix_v3,
        write_probe_artifacts,
    )

    parser = argparse.ArgumentParser(
        description="Run full probe for qa_fetch rename matrix v3 and export evidence artifacts."
    )
    parser.add_argument(
        "--matrix",
        default=DEFAULT_MATRIX_V3_PATH.as_posix(),
        help="Path to matrix markdown file (default: docs/05_data_plane/_draft_qa_fetch_rename_matrix_v3.md)",
    )
    parser.add_argument(
        "--expected-count",
        type=int,
        default=DEFAULT_EXPECTED_COUNT,
        help=f"Expected row count in matrix (default: {DEFAULT_EXPECTED_COUNT})",
    )
    parser.add_argument(
        "--out-dir",
        default=DEFAULT_OUTPUT_DIR.as_posix(),
        help="Output directory for json/csv/candidate files",
    )
    args = parser.parse_args()

    results = probe_matrix_v3(matrix_path=args.matrix, expected_count=args.expected_count)
    paths = write_probe_artifacts(results, out_dir=args.out_dir)

    status_counts: dict[str, int] = {}
    source_counts: dict[str, int] = {}
    for item in results:
        status_counts[item.status] = status_counts.get(item.status, 0) + 1
        source_counts[item.source] = source_counts.get(item.source, 0) + 1

    print("qa_fetch probe done")
    print(f"matrix={args.matrix}")
    print(f"total={len(results)}")
    print("source_counts=", json.dumps(dict(sorted(source_counts.items())), ensure_ascii=False))
    print("status_counts=", json.dumps(dict(sorted(status_counts.items())), ensure_ascii=False))
    for key in [
        "json",
        "csv",
        "candidate_pass_has_data",
        "candidate_pass_has_data_or_empty",
        "summary",
    ]:
        print(f"{key}={paths[key]}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
