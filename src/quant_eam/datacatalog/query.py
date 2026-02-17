from __future__ import annotations

import argparse
import os
from pathlib import Path

from quant_eam.datacatalog.catalog import DataCatalog


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m quant_eam.datacatalog.query")
    parser.add_argument("--root", default=None, help="Data root path (default: env EAM_DATA_ROOT or /data).")
    parser.add_argument("--snapshot-id", required=True)
    parser.add_argument("--symbols", required=True, help="Comma-separated symbols (e.g. AAA,BBB).")
    parser.add_argument("--start", default="2024-01-01")
    parser.add_argument("--end", default="2024-12-31")
    parser.add_argument("--as-of", dest="as_of", required=True, help="ISO datetime with timezone.")
    args = parser.parse_args(argv)

    root = Path(args.root) if args.root else None
    cat = DataCatalog(root=root)
    symbols = [s.strip() for s in args.symbols.split(",")]
    rows, stats = cat.query_ohlcv(
        snapshot_id=args.snapshot_id,
        symbols=symbols,
        start=args.start,
        end=args.end,
        as_of=args.as_of,
    )

    print(f"snapshot_id={args.snapshot_id}")
    print(f"root={cat.root.as_posix()}")
    print(f"symbols={','.join(symbols)}")
    print(f"rows_returned={len(rows)}")
    print(f"rows_before_asof={stats.rows_before_asof}")
    print(f"rows_after_asof={stats.rows_after_asof}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

