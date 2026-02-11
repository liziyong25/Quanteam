from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

from quant_eam.data_lake.lake import DataLake
from quant_eam.policies.load import default_policies_dir, load_yaml


def _load_default_latency_seconds(policies_dir: Path | None = None) -> int:
    policies_dir = policies_dir or default_policies_dir()
    p = policies_dir / "asof_latency_policy_v1.yaml"
    doc: Any = load_yaml(p)
    params = doc.get("params", {}) if isinstance(doc, dict) else {}
    return int(params.get("default_latency_seconds", 0))


def _generate_demo_ohlcv_rows(snapshot_id: str) -> list[dict[str, Any]]:
    # Deterministic, no RNG: values are pure functions of (symbol, dt).
    symbols = ["AAA", "BBB"]
    dts = [f"2024-01-{day:02d}" for day in range(1, 11)]
    rows: list[dict[str, Any]] = []
    for si, sym in enumerate(symbols):
        for di, dt in enumerate(dts):
            base = 100.0 + si * 10.0 + di * 0.1
            rows.append(
                {
                    "symbol": sym,
                    "dt": dt,
                    "open": base,
                    "high": base + 1.0,
                    "low": base - 1.0,
                    "close": base + 0.5,
                    "volume": 1000 + di,
                    # Intentionally omit available_at: DataLake must generate it from asof_latency_policy_v1.
                    "source": "demo",
                    "extensions": {"seed": snapshot_id},
                }
            )
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m quant_eam.data_lake.demo_ingest")
    parser.add_argument("--root", default=None, help="Data root path (default: env EAM_DATA_ROOT or /data).")
    parser.add_argument("--snapshot-id", required=True, help="Snapshot id to write (deterministic).")
    args = parser.parse_args(argv)

    lake = DataLake(root=Path(args.root) if args.root else None)
    rows = _generate_demo_ohlcv_rows(args.snapshot_id)
    manifest = lake.write_ohlcv_1d_snapshot(snapshot_id=args.snapshot_id, rows=rows)

    latency = _load_default_latency_seconds()
    print(f"snapshot_id={manifest['snapshot_id']}")
    print(f"root={lake.root.as_posix()}")
    print(f"default_latency_seconds={latency}")
    ds = manifest["datasets"][0]
    print(f"dataset_id={ds['dataset_id']}")
    print(f"rows={ds['row_count']}")
    print(f"data_file={ds['file']}")
    print(f"manifest_file={lake.manifest_path(args.snapshot_id).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

