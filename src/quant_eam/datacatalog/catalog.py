from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from quant_eam.data_lake.timeutil import parse_daily_dt, parse_iso_datetime, taipei_tz, to_iso


@dataclass(frozen=True)
class QueryStats:
    rows_before_asof: int
    rows_after_asof: int


class DataCatalog:
    def __init__(self, root: Path | None = None) -> None:
        if root is None:
            root = Path(os.getenv("EAM_DATA_ROOT", "/data"))
        self.root = Path(root)

    def _dataset_path(self, snapshot_id: str, dataset_id: str) -> Path:
        return self.root / "lake" / snapshot_id / f"{dataset_id}.csv"

    def query_ohlcv(
        self,
        *,
        snapshot_id: str,
        symbols: list[str],
        start: str,
        end: str,
        as_of: str,
        fields: list[str] | None = None,
        dataset_id: str = "ohlcv_1d",
    ) -> tuple[list[dict[str, Any]], QueryStats]:
        if dataset_id != "ohlcv_1d":
            raise ValueError("Phase-03 MVP only supports dataset_id=ohlcv_1d")

        p = self._dataset_path(snapshot_id, dataset_id)
        if not p.is_file():
            raise FileNotFoundError(p)

        sym_set = {s.strip() for s in symbols if s.strip()}
        if not sym_set:
            raise ValueError("symbols must be non-empty")

        start_dt = parse_daily_dt(start).dt
        end_dt = parse_daily_dt(end).dt
        asof_dt = parse_iso_datetime(as_of)

        rows_before = 0
        rows_after = 0
        out: list[dict[str, Any]] = []
        with p.open("r", newline="", encoding="utf-8") as f:
            r = csv.DictReader(f)
            for row in r:
                sym = str(row.get("symbol", "")).strip()
                if sym not in sym_set:
                    continue

                dt = parse_daily_dt(str(row.get("dt", ""))).dt
                if dt < start_dt or dt > end_dt:
                    continue

                av_raw = str(row.get("available_at", "")).strip()
                av = parse_iso_datetime(av_raw)

                rows_before += 1
                if av <= asof_dt:
                    rows_after += 1
                    out.append(row)

        # Stable sort by (symbol, dt).
        out.sort(key=lambda rr: (str(rr.get("symbol", "")), parse_daily_dt(str(rr.get("dt", ""))).dt))

        if fields:
            keep = set(fields) | {"symbol", "dt"}  # always keep primary keys
            out = [{k: v for k, v in row.items() if k in keep} for row in out]

        return out, QueryStats(rows_before_asof=rows_before, rows_after_asof=rows_after)

