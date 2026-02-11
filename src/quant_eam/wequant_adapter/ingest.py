from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from quant_eam.data_lake.lake import DataLake
from quant_eam.data_lake.timeutil import parse_daily_dt, parse_iso_datetime, taipei_tz, to_iso
from quant_eam.policies.resolve import load_policy_bundle, resolve_asof_latency_policy
from quant_eam.wequant_adapter.client import FakeScenario, FakeWequantClient, RealWequantClient, WequantClientProtocol

EXIT_OK = 0
EXIT_USAGE_OR_ERROR = 1
EXIT_INVALID = 2

INGEST_MANIFEST_SCHEMA_VERSION = "wequant_ingest_manifest_v1"


def _utc_now_iso() -> str:
    sde = os.getenv("SOURCE_DATE_EPOCH")
    if sde and sde.isdigit():
        return datetime.fromtimestamp(int(sde), tz=timezone.utc).isoformat()
    return datetime.now(tz=timezone.utc).isoformat()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass(frozen=True)
class IngestResult:
    snapshot_id: str
    dataset_id: str
    rows_written: int
    data_file: str
    snapshot_manifest: str
    ingest_manifest_file: str
    asof_latency_policy_id: str


def _missing_counts(df: pd.DataFrame, cols: list[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for c in cols:
        if c not in df.columns:
            out[c] = len(df)
            continue
        out[c] = int(df[c].isna().sum())
    return out


def _dedupe_sort(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    if "symbol" not in df.columns or "dt" not in df.columns:
        raise ValueError("source data must include symbol and dt columns")
    before = len(df)
    df2 = df.copy()
    df2["symbol"] = df2["symbol"].astype(str)
    df2["dt"] = df2["dt"].astype(str)
    df2 = df2.sort_values(["symbol", "dt"], kind="mergesort")
    df2 = df2.drop_duplicates(subset=["symbol", "dt"], keep="first")
    dup = before - len(df2)
    return df2.reset_index(drop=True), int(dup)


def _ensure_available_at(
    df: pd.DataFrame, *, asof_policy: dict[str, Any], bar_close_hour: int = 16
) -> tuple[pd.DataFrame, str]:
    params = asof_policy.get("params", {})
    default_latency_seconds = int(params.get("default_latency_seconds", 0))
    bar_close_to_signal_seconds = int(params.get("bar_close_to_signal_seconds", 0))

    df2 = df.copy()
    provided = "available_at" in df2.columns and df2["available_at"].notna().any()

    available_at_values: list[str] = []
    for dt_raw, av_raw in zip(df2["dt"].astype(str).tolist(), df2.get("available_at", pd.Series([None] * len(df2))).tolist()):
        dt_close = parse_daily_dt(dt_raw, bar_close_hour=bar_close_hour).dt
        if av_raw not in (None, "", float("nan")) and str(av_raw).strip() != "nan":
            av = parse_iso_datetime(str(av_raw))
            if av < dt_close:
                raise ValueError("available_at must be >= dt (bar close)")
            available_at_values.append(to_iso(av))
        else:
            av = dt_close + timedelta(seconds=default_latency_seconds + bar_close_to_signal_seconds)
            available_at_values.append(to_iso(av))

    df2["available_at"] = available_at_values
    strategy = "provided_by_source" if provided else "policy_default_latency"
    return df2, strategy


def ingest_ohlcv_1d(
    *,
    client: WequantClientProtocol,
    root: Path,
    snapshot_id: str,
    dataset_id: str,
    symbols: list[str],
    start: str,
    end: str,
    policy_bundle_path: Path,
    dry_run: bool = False,
    frequency: str = "1d",
    fields: list[str] | None = None,
) -> IngestResult:
    if dataset_id != "ohlcv_1d":
        raise ValueError("Phase-03B only supports dataset_id=ohlcv_1d")

    fields = fields or ["open", "high", "low", "close", "volume"]

    bundle_doc = load_policy_bundle(policy_bundle_path)
    asof_pid, asof_policy = resolve_asof_latency_policy(bundle_doc=bundle_doc)

    df = client.fetch_ohlcv(symbols=symbols, start=start, end=end, frequency=frequency, fields=fields)
    if not isinstance(df, pd.DataFrame):
        raise ValueError("client.fetch_ohlcv must return a pandas.DataFrame")

    df_norm = df.copy()
    df_norm["source"] = "wequant"

    required_cols = ["symbol", "dt", "open", "high", "low", "close", "volume"]
    for c in required_cols:
        if c not in df_norm.columns:
            raise ValueError(f"missing required column from client: {c}")

    df_norm, duplicate_count = _dedupe_sort(df_norm)
    df_norm, available_at_strategy = _ensure_available_at(df_norm, asof_policy=asof_policy)

    rows_in = int(len(df))
    rows_out = int(len(df_norm))
    missing_count_by_column = _missing_counts(df_norm, required_cols + ["available_at"])

    lake = DataLake(root=root)
    snap_dir = lake.snapshot_dir(snapshot_id)
    data_file = lake.dataset_csv_path(snapshot_id, dataset_id)
    snapshot_manifest = lake.manifest_path(snapshot_id)
    ingest_dir = snap_dir / "ingest_manifests"
    ingest_manifest_file = ingest_dir / f"{dataset_id}_wequant_ingest.json"

    if not dry_run:
        # Use DataLake writer to ensure Phase-03 manifest format and dt parsing are consistent.
        rows = df_norm.to_dict(orient="records")
        lake.write_ohlcv_1d_snapshot(snapshot_id=snapshot_id, rows=rows, dataset_id=dataset_id)
        ingest_dir.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, Any] = {
        "schema_version": INGEST_MANIFEST_SCHEMA_VERSION,
        "snapshot_id": snapshot_id,
        "dataset_id": dataset_id,
        "source": "wequant",
        "symbols": symbols,
        "start": start,
        "end": end,
        "frequency": frequency,
        "fields": fields,
        "fetched_at": _utc_now_iso(),
        "asof_latency_policy_id": asof_pid,
        "available_at_strategy": available_at_strategy,
        "rows_in": rows_in,
        "rows_out": rows_out,
        "duplicate_count": duplicate_count,
        "missing_count_by_column": missing_count_by_column,
        "output_paths": {
            "data_file": data_file.as_posix(),
            "snapshot_manifest": snapshot_manifest.as_posix(),
            "ingest_manifest_file": ingest_manifest_file.as_posix(),
        },
    }

    if not dry_run:
        manifest["sha256_of_data_file"] = _sha256_file(data_file)
        ingest_manifest_file.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return IngestResult(
        snapshot_id=snapshot_id,
        dataset_id=dataset_id,
        rows_written=rows_out if not dry_run else 0,
        data_file=data_file.as_posix(),
        snapshot_manifest=snapshot_manifest.as_posix(),
        ingest_manifest_file=ingest_manifest_file.as_posix(),
        asof_latency_policy_id=asof_pid,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m quant_eam.wequant_adapter.ingest")
    parser.add_argument("--client", choices=["real", "fake"], default="real")
    parser.add_argument("--root", default=None, help="Data root (default: env EAM_DATA_ROOT or /data).")
    parser.add_argument("--snapshot-id", required=True)
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--symbols", required=True, help="Comma-separated symbols (e.g. AAA,BBB).")
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--policy-bundle", required=True, help="Path to policy_bundle_v1.yaml")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    try:
        root = Path(args.root) if args.root else Path(os.getenv("EAM_DATA_ROOT", "/data"))
        symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
        if not symbols:
            print("ERROR: symbols must be non-empty", file=sys.stderr)
            return EXIT_USAGE_OR_ERROR

        if args.client == "fake":
            client: WequantClientProtocol = FakeWequantClient(FakeScenario(include_available_at=False))
        else:
            client = RealWequantClient()

        res = ingest_ohlcv_1d(
            client=client,
            root=root,
            snapshot_id=args.snapshot_id,
            dataset_id=args.dataset_id,
            symbols=symbols,
            start=args.start,
            end=args.end,
            policy_bundle_path=Path(args.policy_bundle),
            dry_run=bool(args.dry_run),
        )

        print(f"snapshot_id={res.snapshot_id}")
        print(f"dataset_id={res.dataset_id}")
        print(f"rows_written={res.rows_written}")
        print(f"data_file={res.data_file}")
        print(f"snapshot_manifest={res.snapshot_manifest}")
        print(f"ingest_manifest_file={res.ingest_manifest_file}")
        print(f"asof_latency_policy_id={res.asof_latency_policy_id}")
        return EXIT_OK
    except ValueError as e:
        print(f"INVALID: {e}", file=sys.stderr)
        return EXIT_INVALID
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: {e}", file=sys.stderr)
        return EXIT_USAGE_OR_ERROR


if __name__ == "__main__":
    raise SystemExit(main())

