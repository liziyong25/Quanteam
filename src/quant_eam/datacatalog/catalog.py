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


MARKET_ASOF_HINTS = ("_day", "_min", "_transaction", "_tick", "_dk", "ohlcv")


class DataCatalog:
    def __init__(self, root: Path | None = None) -> None:
        if root is None:
            root = Path(os.getenv("EAM_DATA_ROOT", "/data"))
        self.root = Path(root)

    def _dataset_path(self, snapshot_id: str, dataset_id: str) -> Path:
        return self.root / "lake" / snapshot_id / f"{dataset_id}.csv"

    def _read_dataset_rows(self, *, snapshot_id: str, dataset_id: str) -> list[dict[str, Any]]:
        path = self._dataset_path(snapshot_id, dataset_id)
        if not path.is_file():
            raise FileNotFoundError(path)
        with path.open("r", newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    @staticmethod
    def _is_market_dataset(dataset_id: str) -> bool:
        token = str(dataset_id).strip().lower()
        return any(hint in token for hint in MARKET_ASOF_HINTS)

    @staticmethod
    def _match_filter(value: Any, condition: Any) -> bool:
        if isinstance(condition, dict):
            val = "" if value is None else str(value)
            if "eq" in condition:
                return str(condition["eq"]) == val
            lower_ok = True
            upper_ok = True
            if "gte" in condition:
                lower_ok = val >= str(condition["gte"])
            if "lte" in condition:
                upper_ok = val <= str(condition["lte"])
            return lower_ok and upper_ok
        if isinstance(condition, list):
            return str(value) in {str(v) for v in condition}
        return str(value) == str(condition)

    @staticmethod
    def _infer_dtypes(rows: list[dict[str, Any]]) -> dict[str, str]:
        if not rows:
            return {}
        sample = rows[: min(200, len(rows))]
        out: dict[str, str] = {}
        columns = list(sample[0].keys())
        for col in columns:
            vals = [row.get(col) for row in sample if row.get(col) not in (None, "")]
            if not vals:
                out[col] = "object"
                continue
            is_int = True
            is_float = True
            is_datetime = True
            for raw in vals:
                text = str(raw)
                if is_int:
                    try:
                        int(float(text))
                    except Exception:
                        is_int = False
                if is_float:
                    try:
                        float(text)
                    except Exception:
                        is_float = False
                if is_datetime:
                    try:
                        parse_iso_datetime(text)
                    except Exception:
                        try:
                            parse_daily_dt(text)
                        except Exception:
                            is_datetime = False
            if is_datetime:
                out[col] = "datetime64[ns]"
            elif is_int:
                out[col] = "int64"
            elif is_float:
                out[col] = "float64"
            else:
                out[col] = "object"
        return out

    def query_dataset(
        self,
        *,
        snapshot_id: str,
        dataset_id: str,
        filters: dict[str, Any] | None,
        as_of: str,
        fields: list[str] | None = None,
        adjust: str = "raw",
    ) -> dict[str, Any]:
        if adjust not in {"raw", "qfq", "hfq"}:
            raise ValueError("adjust must be one of raw|qfq|hfq")

        rows = self._read_dataset_rows(snapshot_id=snapshot_id, dataset_id=dataset_id)
        rows_before_filter = len(rows)
        applied_filters = filters or {}
        if applied_filters:
            filtered: list[dict[str, Any]] = []
            for row in rows:
                ok = True
                for field, cond in applied_filters.items():
                    if not self._match_filter(row.get(field), cond):
                        ok = False
                        break
                if ok:
                    filtered.append(row)
            rows = filtered

        rows_before_asof = len(rows)
        asof_dt = parse_iso_datetime(as_of)
        warnings: list[str] = []
        is_market = self._is_market_dataset(dataset_id)
        has_available_at = any(str(r.get("available_at", "")).strip() for r in rows)
        if is_market and has_available_at:
            gated: list[dict[str, Any]] = []
            for row in rows:
                av_raw = str(row.get("available_at", "")).strip()
                if not av_raw:
                    continue
                try:
                    av = parse_iso_datetime(av_raw)
                except Exception:
                    continue
                if av <= asof_dt:
                    gated.append(row)
            rows = gated
            as_of_applied = {
                "rule": "available_at<=as_of",
                "as_of": to_iso(asof_dt),
                "applied": True,
                "mode": "market",
                "rows_before_asof": rows_before_asof,
                "rows_after_asof": len(rows),
            }
        elif is_market:
            as_of_applied = {
                "rule": "available_at<=as_of",
                "as_of": to_iso(asof_dt),
                "applied": False,
                "mode": "market",
                "rows_before_asof": rows_before_asof,
                "rows_after_asof": len(rows),
            }
            warnings.append("available_at missing; market as_of gate skipped")
        else:
            as_of_applied = {
                "rule": "snapshot_effective_time",
                "as_of": to_iso(asof_dt),
                "applied": False,
                "mode": "reference",
                "rows_before_asof": rows_before_asof,
                "rows_after_asof": len(rows),
            }

        if fields:
            keep = set(fields)
            for key in ("symbol", "dt", "trade_date", "code", "available_at"):
                if any(key in row for row in rows):
                    keep.add(key)
            rows = [{k: v for k, v in row.items() if k in keep} for row in rows]

        dtypes = self._infer_dtypes(rows)
        columns = list(rows[0].keys()) if rows else (list(fields) if fields else [])
        return {
            "schema_version": "qa_dataset_query_result_v1",
            "dataset_id": dataset_id,
            "snapshot_id": snapshot_id,
            "adjust": adjust,
            "rows": rows,
            "row_count": len(rows),
            "columns": columns,
            "dtypes": dtypes,
            "as_of_applied": as_of_applied,
            "source_lineage": {
                "dataset_file": self._dataset_path(snapshot_id, dataset_id).as_posix(),
                "rows_before_filter": rows_before_filter,
                "rows_after_filter": rows_before_asof,
                "filters": applied_filters,
            },
            "warnings": warnings,
            "errors": [],
        }

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
        sym_set = {s.strip() for s in symbols if s.strip()}
        if not sym_set:
            raise ValueError("symbols must be non-empty")
        result = self.query_dataset(
            snapshot_id=snapshot_id,
            dataset_id=dataset_id,
            filters={
                "symbol": sorted(sym_set),
                "dt": {"gte": str(start), "lte": str(end)},
            },
            as_of=as_of,
            fields=fields,
            adjust="raw",
        )
        rows = list(result.get("rows", []))
        rows.sort(key=lambda rr: (str(rr.get("symbol", "")), parse_daily_dt(str(rr.get("dt", ""))).dt))
        asof_meta = result.get("as_of_applied", {}) if isinstance(result, dict) else {}
        rows_before = int(asof_meta.get("rows_before_asof", len(rows)))
        rows_after = int(asof_meta.get("rows_after_asof", len(rows)))
        return rows, QueryStats(rows_before_asof=rows_before, rows_after_asof=rows_after)
