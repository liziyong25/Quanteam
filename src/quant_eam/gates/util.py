from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from quant_eam.datacatalog.catalog import DataCatalog
from quant_eam.data_lake.timeutil import parse_iso_datetime


@dataclass(frozen=True)
class Segment:
    start: str
    end: str
    as_of: str


def extract_symbols(runspec: dict[str, Any]) -> list[str]:
    syms = (runspec.get("extensions", {}) or {}).get("symbols", [])
    if not isinstance(syms, list):
        return []
    out = [str(s).strip() for s in syms]
    return [s for s in out if s]


def extract_segment(runspec: dict[str, Any], name: str) -> Segment | None:
    segs = runspec.get("segments", {}) if isinstance(runspec, dict) else {}
    seg = segs.get(name, {}) if isinstance(segs, dict) else {}
    if not isinstance(seg, dict):
        return None
    start = str(seg.get("start", "")).strip()
    end = str(seg.get("end", "")).strip()
    as_of = str(seg.get("as_of", "")).strip()
    if not start or not end or not as_of:
        return None
    return Segment(start=start, end=end, as_of=as_of)


def query_prices_df(
    *,
    data_root: Path | None,
    snapshot_id: str,
    symbols: list[str],
    seg: Segment,
    dataset_id: str = "ohlcv_1d",
) -> tuple[pd.DataFrame, dict[str, int]]:
    cat = DataCatalog(root=data_root)
    rows, stats = cat.query_ohlcv(
        snapshot_id=snapshot_id,
        symbols=symbols,
        start=seg.start,
        end=seg.end,
        as_of=seg.as_of,
        dataset_id=dataset_id,
    )
    if not rows:
        raise ValueError("DataCatalog query returned 0 rows")

    df = pd.DataFrame.from_records(rows)
    for c in ["open", "high", "low", "close", "volume"]:
        if c in df.columns:
            df[c] = df[c].astype(float)
    df["dt"] = df["dt"].astype(str)
    df["symbol"] = df["symbol"].astype(str)
    # Ensure determinism: stable sort.
    df = df.sort_values(["symbol", "dt"], kind="mergesort").reset_index(drop=True)

    return df, {"rows_before_asof": int(stats.rows_before_asof), "rows_after_asof": int(stats.rows_after_asof)}


def count_asof_violations(df: pd.DataFrame, as_of: str) -> int:
    asof_dt = parse_iso_datetime(as_of)
    v = 0
    for av_raw in df.get("available_at", pd.Series([], dtype=str)).astype(str).tolist():
        try:
            if parse_iso_datetime(str(av_raw)) > asof_dt:
                v += 1
        except Exception:
            v += 1
    return int(v)

